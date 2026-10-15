"""Audio ingestion, WhisperX transcription, and speaker diarization engine for MediScribe AI."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Supported formats and size limit
SUPPORTED_EXTENSIONS = {".mp3", ".wav"}
DEFAULT_MAX_AUDIO_BYTES = 50 * 1024 * 1024  # 50 MB default

# ---------------------------------------------------------------------------
# FFmpeg PATH resolution
# ---------------------------------------------------------------------------
# whisperx.load_audio() invokes the bare "ffmpeg" command via subprocess.
# On Windows ffmpeg is often installed to a non-standard location.  We read
# FFMPEG_PATH from the environment (set it in .env) and, if present, prepend
# its parent directory to PATH so that every subprocess can find the binary.
# We also probe a set of well-known Windows install locations as a fallback.

_FALLBACK_FFMPEG_PATHS: list[str] = [
    # Common manual-extract locations on Windows
    r"C:\Users\tejas\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
]


def _resolve_ffmpeg() -> str | None:
    """Return the first usable ffmpeg executable path (or None).

    Checks (in order):
    1. ``ffmpeg`` already on PATH.
    2. ``FFMPEG_PATH`` environment variable (re-read each call so dotenv works).
    3. Known Windows install locations.
    """
    # 1. Already on PATH?
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 2. FFMPEG_PATH env var (read dynamically so dotenv loading order doesn't matter)
    env_path = os.getenv("FFMPEG_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    # 3. Check known locations
    for candidate in _FALLBACK_FFMPEG_PATHS:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _ensure_ffmpeg_on_path() -> None:
    """Prepend the ffmpeg binary's directory to PATH if not already resolvable."""
    if shutil.which("ffmpeg"):
        return  # Already on PATH — nothing to do
    exe = _resolve_ffmpeg()
    if exe:
        ffmpeg_dir = str(Path(exe).parent)
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path


# Patch PATH as early as possible so whisperx subprocess calls succeed
_ensure_ffmpeg_on_path()


@dataclass
class AudioValidationResult:
    is_valid: bool
    error_message: str | None = None
    file_size_bytes: int = 0
    file_extension: str = ""


@dataclass
class AudioSegment:
    segment_id: str
    speaker_id: str  # e.g., "SPEAKER_00", "SPEAKER_01"
    start_sec: float
    end_sec: float
    text: str
    confidence: float = 0.95


@dataclass
class AudioJob:
    job_id: str
    filename: str
    status: str  # "queued", "validating", "transcribing", "diarizing", "completed", "failed"
    progress: int  # 0 to 100
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    segments: list[dict[str, Any]] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    error_message: str | None = None
    diarization_warning: str | None = None
    duration_sec: float = 0.0


class AudioJobManager:
    """Thread-safe in-memory manager for background audio processing jobs."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._jobs: dict[str, AudioJob] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def create_job(self, filename: str) -> AudioJob:
        job_id = f"aud-{uuid.uuid4().hex[:12]}"
        job = AudioJob(
            job_id=job_id,
            filename=filename,
            status="queued",
            progress=5,
        )
        with self._lock:
            self._cleanup_old_jobs()
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> AudioJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: str | None = None,
        progress: int | None = None,
        segments: list[dict[str, Any]] | None = None,
        speakers: list[str] | None = None,
        error_message: str | None = None,
        diarization_warning: str | None = None,
        duration_sec: float | None = None,
    ) -> AudioJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if segments is not None:
                job.segments = segments
            if speakers is not None:
                job.speakers = speakers
            if error_message is not None:
                job.error_message = error_message
            if diarization_warning is not None:
                job.diarization_warning = diarization_warning
            if duration_sec is not None:
                job.duration_sec = duration_sec
            job.updated_at = time.time()
            return job

    def _cleanup_old_jobs(self) -> None:
        now = time.time()
        expired = [
            jid for jid, j in self._jobs.items()
            if (now - j.updated_at) >= self._ttl_seconds
        ]
        for jid in expired:
            del self._jobs[jid]


# Global job manager
job_manager = AudioJobManager()

# Global cached WhisperX model references (to avoid reloading multiple large models)
_model_lock = threading.Lock()
_cached_whisper_model: Any = None
_cached_whisper_config: tuple[str, str, str] | None = None  # (model_name, device, compute_type)


def check_audio_dependencies() -> dict[str, Any]:
    """Inspect environment for whisperx, pyannote.audio, torch, ffmpeg, and HF_TOKEN."""
    # Re-run path patching in case the environment changed since module load
    _ensure_ffmpeg_on_path()

    has_whisperx = False
    whisperx_version = None
    whisperx_import_error: str | None = None
    has_torch = False
    has_ffmpeg = bool(shutil.which("ffmpeg")) or bool(_resolve_ffmpeg())
    ffmpeg_path = shutil.which("ffmpeg") or _resolve_ffmpeg() or ""
    has_hf_token = bool(os.getenv("HF_TOKEN", "").strip())

    try:
        import torch  # type: ignore
        has_torch = True
    except ImportError as exc:
        whisperx_import_error = str(exc)  # surface torch errors too

    try:
        import whisperx  # type: ignore
        has_whisperx = True
        whisperx_version = getattr(whisperx, "__version__", "installed")
    except Exception as exc:  # noqa: BLE001
        whisperx_import_error = str(exc)

    return {
        "has_whisperx": has_whisperx,
        "whisperx_version": whisperx_version,
        "whisperx_import_error": whisperx_import_error,
        "has_torch": has_torch,
        "has_ffmpeg": has_ffmpeg,
        "ffmpeg_path": ffmpeg_path,
        "has_hf_token": has_hf_token,
        "required_gated_models": [
            "pyannote/speaker-diarization-3.1",
            "pyannote/segmentation-3.0",
        ],
    }


def validate_audio_file(
    filename: str,
    file_bytes: bytes,
    max_bytes: int = DEFAULT_MAX_AUDIO_BYTES,
) -> AudioValidationResult:
    """Validate audio filename, extension, and content size."""
    if not filename or not filename.strip():
        return AudioValidationResult(
            is_valid=False,
            error_message="No audio filename provided.",
        )

    # Sanitize path traversal
    safe_name = Path(filename).name
    ext = Path(safe_name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        return AudioValidationResult(
            is_valid=False,
            error_message=(
                f"Unsupported audio format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}. "
                "Please upload an MP3 or WAV recording."
            ),
            file_extension=ext,
            file_size_bytes=len(file_bytes),
        )

    size = len(file_bytes)
    if size == 0:
        return AudioValidationResult(
            is_valid=False,
            error_message="Uploaded audio file is empty (0 bytes).",
            file_extension=ext,
            file_size_bytes=0,
        )

    if size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        curr_mb = size / (1024 * 1024)
        return AudioValidationResult(
            is_valid=False,
            error_message=f"File size ({curr_mb:.1f} MB) exceeds maximum allowed size of {max_mb} MB.",
            file_extension=ext,
            file_size_bytes=size,
        )

    return AudioValidationResult(
        is_valid=True,
        file_size_bytes=size,
        file_extension=ext,
    )


def get_whisperx_model(
    model_name: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
) -> Any:
    """Retrieve or load cached WhisperX transcription model."""
    global _cached_whisper_model, _cached_whisper_config

    with _model_lock:
        if _cached_whisper_model is not None and _cached_whisper_config == (model_name, device, compute_type):
            return _cached_whisper_model

        import whisperx  # type: ignore

        # Load model using int8 quantization and CPU execution
        model = whisperx.load_model(model_name, device, compute_type=compute_type)
        _cached_whisper_model = model
        _cached_whisper_config = (model_name, device, compute_type)
        return model


def process_audio_file(
    audio_path: str,
    job_id: str,
    hf_token: str | None = None,
    model_name: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
) -> None:
    """Background worker task for WhisperX transcription + speaker diarization.
    
    If WhisperX or FFmpeg is missing from the environment, sets an informative error
    with clear diagnosis. If transcription succeeds but diarization fails (e.g. missing HF_TOKEN
    or gated model approval), preserves transcription results with a clear diarization_warning.
    """
    job_manager.update_job(job_id, status="transcribing", progress=20)

    deps = check_audio_dependencies()
    if not deps["has_ffmpeg"]:
        job_manager.update_job(
            job_id,
            status="failed",
            error_message=(
                "FFmpeg is not installed or not available on the system PATH. "
                "WhisperX requires FFmpeg to decode audio streams. "
                "Please install FFmpeg and restart the server."
            ),
        )
        return

    if not deps["has_whisperx"]:
        job_manager.update_job(
            job_id,
            status="failed",
            error_message=(
                "WhisperX is not installed in the Python environment. "
                "Please install dependencies via: pip install whisperx pyannote-audio"
            ),
        )
        return

    try:
        import whisperx  # type: ignore

        # 1. Load audio — ensure ffmpeg is still on PATH (the thread inherits env)
        _ensure_ffmpeg_on_path()
        job_manager.update_job(job_id, progress=30)
        try:
            audio = whisperx.load_audio(audio_path)
        except Exception as load_err:
            job_manager.update_job(
                job_id,
                status="failed",
                error_message=(
                    f"Failed to decode audio file. "
                    f"Ensure FFmpeg is installed and accessible. "
                    f"Error: {load_err}"
                ),
            )
            return
        duration_sec = len(audio) / 16000.0
        job_manager.update_job(job_id, duration_sec=duration_sec)

        # 2. Transcribe
        job_manager.update_job(job_id, progress=45)
        model = get_whisperx_model(model_name=model_name, device=device, compute_type=compute_type)
        result = model.transcribe(audio, batch_size=8)

        # 3. Align whisper output (if alignment model is available)
        job_manager.update_job(job_id, progress=60)
        try:
            align_model, metadata = whisperx.load_align_model(
                language_code=result.get("language", "en"),
                device=device,
            )
            result = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
        except Exception as align_err:
            # Alignment is an enhancement; proceed if alignment fails
            pass

        # 4. Speaker Diarization
        job_manager.update_job(job_id, status="diarizing", progress=75)
        token = (hf_token or os.getenv("HF_TOKEN", "")).strip()
        diarization_warning = None

        if not token:
            diarization_warning = (
                "Speaker diarization was skipped because HF_TOKEN is not set. "
                "To enable speaker diarization, accept pyannote conditions on Hugging Face "
                "(pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0) and set HF_TOKEN in .env."
            )
        else:
            try:
                diarize_pipeline = whisperx.DiarizationPipeline(
                    use_auth_token=token,
                    device=device,
                )
                diarize_segments = diarize_pipeline(audio_path)
                result = whisperx.assign_word_speakers(diarize_segments, result)
            except Exception as diar_err:
                err_str = str(diar_err)
                if "401" in err_str or "unauthorized" in err_str.lower():
                    diarization_warning = (
                        "Hugging Face authentication failed (401 Unauthorized). "
                        "Please verify your HF_TOKEN in .env has valid Read permissions."
                    )
                elif "403" in err_str or "gated" in err_str.lower() or "pyannote" in err_str.lower():
                    diarization_warning = (
                        "Access to pyannote gated models is forbidden (403). "
                        "Please visit https://huggingface.co/pyannote/speaker-diarization-3.1 and "
                        "https://huggingface.co/pyannote/segmentation-3.0 to accept the model terms."
                    )
                else:
                    diarization_warning = f"Speaker diarization encountered an issue: {err_str}"

        # 5. Format segments
        raw_segments = result.get("segments", [])
        formatted_segments = []
        unique_speakers = set()

        for idx, seg in enumerate(raw_segments):
            speaker = seg.get("speaker", f"SPEAKER_{idx % 2:02d}")
            unique_speakers.add(speaker)
            formatted_segments.append({
                "segment_id": f"seg_{idx + 1:03d}",
                "speaker_id": speaker,
                "role": "unknown",  # Initial role is unassigned
                "start_sec": round(seg.get("start", 0.0), 2),
                "end_sec": round(seg.get("end", 0.0), 2),
                "text": seg.get("text", "").strip(),
            })

        # Complete job
        job_manager.update_job(
            job_id,
            status="completed",
            progress=100,
            segments=formatted_segments,
            speakers=sorted(list(unique_speakers)),
            diarization_warning=diarization_warning,
        )

    except Exception as exc:  # noqa: BLE001
        import traceback
        job_manager.update_job(
            job_id,
            status="failed",
            error_message=f"Audio processing error: {type(exc).__name__}: {exc}",
        )
        # Print the full traceback to server logs for debugging
        traceback.print_exc()
