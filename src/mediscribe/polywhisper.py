"""PolyWhisper Hinglish ASR Engine for MediScribe AI.

Provides speech-to-text transcription for Hindi-English code-mixed (Hinglish)
clinical dialogue using the fine-tuned PolyWhisper LoRA adapter on openai/whisper-small.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from transformers import WhisperForConditionalGeneration, WhisperProcessor


class PolyWhisperV3(nn.Module):
    """Whisper backbone equipped with modular low-rank (LoRA) adapter projections."""

    PROJ_MAP = [
        ("self_attn", "self_q"),
        ("self_attn", "self_k"),
        ("self_attn", "self_v"),
        ("encoder_attn", "cross_q"),
        ("encoder_attn", "cross_k"),
        ("encoder_attn", "cross_v"),
        ("self_attn", "self_out"),
        ("encoder_attn", "cross_out"),
    ]
    ENC_PROJ_MAP = [
        ("self_attn", "enc_q"),
        ("self_attn", "enc_k"),
        ("self_attn", "enc_v"),
        ("self_attn", "enc_out"),
    ]

    def __init__(
        self,
        whisper_name: str = "openai/whisper-small",
        rank: int = 16,
        encoder_lora: bool = True,
        device: str = "cpu",
    ) -> None:
        super().__init__()
        self.rank = rank
        self.encoder_lora = encoder_lora
        self.device = torch.device(device)

        self.whisper = WhisperForConditionalGeneration.from_pretrained(whisper_name).to(self.device)
        for p in self.whisper.parameters():
            p.requires_grad = False

        self.d_model = self.whisper.config.d_model
        self.decoder_layers = self.whisper.config.decoder_layers
        self.encoder_layers = self.whisper.config.encoder_layers
        self.lora_adapters = nn.ModuleDict()
        self._lora_hooks: list[Any] = []
        self._current_lang: str | None = None

    def add_language(self, lang: str) -> nn.ModuleDict:
        d, r = self.d_model, self.rank
        adpt = nn.ModuleDict()
        for i in range(self.decoder_layers):
            for _, base_name in self.PROJ_MAP:
                adpt[f"d{i}_{base_name}_a"] = nn.Linear(d, r, bias=False).to(self.device)
                adpt[f"d{i}_{base_name}_b"] = nn.Linear(r, d, bias=False).to(self.device)
                nn.init.zeros_(adpt[f"d{i}_{base_name}_b"].weight)
        if self.encoder_lora:
            for i in range(self.encoder_layers):
                for _, base_name in self.ENC_PROJ_MAP:
                    adpt[f"e{i}_{base_name}_a"] = nn.Linear(d, r, bias=False).to(self.device)
                    adpt[f"e{i}_{base_name}_b"] = nn.Linear(r, d, bias=False).to(self.device)
                    nn.init.zeros_(adpt[f"e{i}_{base_name}_b"].weight)
        self.lora_adapters[lang] = adpt
        return adpt

    @staticmethod
    def _proj_name(base_name: str) -> str:
        if "out" in base_name:
            return "out_proj"
        if "q" in base_name:
            return "q_proj"
        if "k" in base_name:
            return "k_proj"
        return "v_proj"

    def set_language(self, lang: str) -> None:
        if self._current_lang == lang:
            return
        self._remove_lora_hooks()
        if lang not in self.lora_adapters:
            self.add_language(lang)
        lora = self.lora_adapters[lang]
        self._lora_hooks = []
        for i, layer in enumerate(self.whisper.model.decoder.layers):
            for attn_name, base_name in self.PROJ_MAP:
                a = lora[f"d{i}_{base_name}_a"]
                b = lora[f"d{i}_{base_name}_b"]

                def make_hook(a_layer: nn.Linear, b_layer: nn.Linear):
                    def hook(mod: Any, inp: Any, out: Any):
                        return out + b_layer(a_layer(inp[0]))

                    return hook

                proj = getattr(getattr(layer, attn_name), self._proj_name(base_name))
                self._lora_hooks.append(proj.register_forward_hook(make_hook(a, b)))

        if self.encoder_lora:
            for i, layer in enumerate(self.whisper.model.encoder.layers):
                for attn_name, base_name in self.ENC_PROJ_MAP:
                    a = lora[f"e{i}_{base_name}_a"]
                    b = lora[f"e{i}_{base_name}_b"]
                    proj = getattr(getattr(layer, attn_name), self._proj_name(base_name))
                    self._lora_hooks.append(proj.register_forward_hook(make_hook(a, b)))
        self._current_lang = lang

    def _remove_lora_hooks(self) -> None:
        for handle in self._lora_hooks:
            handle.remove()
        self._lora_hooks = []

    def load_adapter(self, lang: str, path: str | Path) -> None:
        if lang not in self.lora_adapters:
            self.add_language(lang)
        st = torch.load(path, map_location=self.device, weights_only=True)
        self.lora_adapters[lang].load_state_dict(st)

    @torch.no_grad()
    def generate(self, feat: torch.Tensor, lang: str, **kwargs: Any) -> Any:
        self.set_language(lang)
        return self.whisper.generate(feat, **kwargs)


def _load_audio_array(audio_path: str | Path, target_sr: int = 16000) -> tuple[np.ndarray, float]:
    """Load an audio file into a 1D float32 numpy array normalized to [-1, 1] at target_sr."""
    path = Path(audio_path)
    suffix = path.suffix.lower()

    if suffix == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)

            if sampwidth == 2:
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 4:
                samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            elif sampwidth == 1:
                samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                raise ValueError(f"Unsupported sample width: {sampwidth}")

            if n_channels > 1:
                samples = samples.reshape(-1, n_channels).mean(axis=1)

            # Simple resample if needed
            if framerate != target_sr:
                new_len = int(len(samples) * target_sr / framerate)
                indices = np.linspace(0, len(samples) - 1, new_len)
                samples = np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)

            duration = len(samples) / float(target_sr)
            return samples, duration
        except Exception:
            pass  # Fall through to ffmpeg/soundfile if custom wave reader hits edge case

    # Fallback to ffmpeg conversion if available
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                str(target_sr),
                "-f",
                "wav",
                tmp_path,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            with wave.open(tmp_path, "rb") as wf:
                raw = wf.readframes(wf.getnframes())
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            duration = len(samples) / float(target_sr)
            return samples, duration
        finally:
            if Path(tmp_path).exists():
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # Fallback to soundfile if installed
    try:
        import soundfile as sf
        samples, sr = sf.read(str(path))
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        samples = samples.astype(np.float32)
        if sr != target_sr:
            new_len = int(len(samples) * target_sr / sr)
            indices = np.linspace(0, len(samples) - 1, new_len)
            samples = np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)
        return samples, len(samples) / float(target_sr)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to decode audio file '{path.name}'. For WAV files, ensure standard PCM format. "
            f"For MP3 files, ensure FFmpeg is installed on your system. Details: {exc}"
        ) from exc


def _split_into_chunks(
    audio: np.ndarray,
    sr: int = 16000,
    target_chunk_s: float = 20.0,
    min_chunk_s: float = 8.0,
    max_chunk_s: float = 28.0,
) -> list[tuple[int, int]]:
    """Split audio array into chunk index slices aligning with quiet pauses."""
    total_len = len(audio)
    min_samples = int(min_chunk_s * sr)
    max_samples = int(max_chunk_s * sr)

    chunks: list[tuple[int, int]] = []
    curr = 0

    while curr < total_len:
        if total_len - curr <= max_samples:
            chunks.append((curr, total_len))
            break

        search_start = curr + min_samples
        search_end = min(curr + max_samples, total_len)
        slice_to_search = audio[search_start:search_end]
        frame_len = int(sr * 0.05)  # 50ms frames
        n_frames = len(slice_to_search) // frame_len

        if n_frames > 0:
            energies = [
                float(np.mean(slice_to_search[i * frame_len : (i + 1) * frame_len] ** 2))
                for i in range(n_frames)
            ]
            split_offset = int(np.argmin(energies)) * frame_len
            split_pt = search_start + split_offset
        else:
            split_pt = search_end

        chunks.append((curr, split_pt))
        curr = split_pt

    return chunks


class HinglishTranscriber:
    """Manages Hinglish PolyWhisper model caching and transcription execution."""

    def __init__(
        self,
        adapter_path: str | Path | None = None,
        whisper_name: str = "openai/whisper-small",
        device: str = "cpu",
    ) -> None:
        self.whisper_name = whisper_name
        self.device = device
        self.adapter_path = Path(adapter_path) if adapter_path else self._find_adapter()
        self._model: PolyWhisperV3 | None = None
        self._processor: WhisperProcessor | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _find_adapter() -> Path:
        """Locate the hinglish_adapter.zip or .pt file."""
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "models" / "hinglish_adapter.zip",
            Path(__file__).resolve().parent.parent.parent / "models" / "hinglish_adapter.pt",
            Path("models/hinglish_adapter.zip"),
            Path("models/hinglish_adapter.pt"),
        ]
        for c in candidates:
            if c.is_file():
                return c
        return candidates[0]

    def is_available(self) -> bool:
        """Check whether the model weights and adapter are present."""
        return self.adapter_path.is_file()

    def _ensure_loaded(self) -> tuple[PolyWhisperV3, WhisperProcessor]:
        with self._lock:
            if self._model is not None and self._processor is not None:
                return self._model, self._processor

            if not self.adapter_path.is_file():
                raise FileNotFoundError(
                    f"Hinglish adapter weights not found at: {self.adapter_path}. "
                    "Ensure models/hinglish_adapter.zip is present."
                )

            processor = WhisperProcessor.from_pretrained(self.whisper_name)
            model = PolyWhisperV3(whisper_name=self.whisper_name, rank=16, encoder_lora=True, device=self.device)
            model.load_adapter("hinglish", self.adapter_path)
            model.eval()

            self._model = model
            self._processor = processor
            return model, processor

    def transcribe_file(
        self,
        audio_path: str | Path,
        progress_callback: Any = None,
    ) -> tuple[list[dict[str, Any]], float]:
        """Transcribe an audio file and return a list of segment dicts with start/end timestamps."""
        model, processor = self._ensure_loaded()
        audio, duration_sec = _load_audio_array(audio_path, target_sr=16000)

        chunks = _split_into_chunks(audio, sr=16000)
        segments: list[dict[str, Any]] = []

        total_chunks = len(chunks)
        for idx, (c_start, c_end) in enumerate(chunks):
            start_s = round(c_start / 16000.0, 2)
            end_s = round(c_end / 16000.0, 2)
            chunk_samples = audio[c_start:c_end]

            # Skip pure silence chunks
            if len(chunk_samples) < 1600 or np.max(np.abs(chunk_samples)) < 0.005:
                continue

            features = processor.feature_extractor(
                [chunk_samples],
                sampling_rate=16000,
                return_tensors="pt",
            ).input_features.to(model.device)

            with torch.no_grad():
                tokens = model.generate(
                    features,
                    lang="hinglish",
                    language="hi",
                    task="transcribe",
                    max_new_tokens=128,
                    num_beams=1,
                    repetition_penalty=1.2,
                    no_repeat_ngram_size=3,
                )

            text = processor.decode(tokens[0], skip_special_tokens=True).strip()
            # Clean non-printable / replacement characters
            text = text.replace("\ufffd", "").strip()

            if text:
                segments.append({
                    "start": start_s,
                    "end": end_s,
                    "text": text,
                })

            if progress_callback:
                progress_pct = int(30 + 40 * (idx + 1) / max(1, total_chunks))
                progress_callback(progress_pct)

        return segments, duration_sec


# Global singleton instance
_hinglish_transcriber: HinglishTranscriber | None = None
_transcriber_lock = threading.Lock()


def get_hinglish_transcriber() -> HinglishTranscriber:
    global _hinglish_transcriber
    with _transcriber_lock:
        if _hinglish_transcriber is None:
            adapter_env = os.getenv("HINGLISH_ADAPTER_PATH", "").strip()
            adapter_path = Path(adapter_env) if adapter_env else None
            _hinglish_transcriber = HinglishTranscriber(adapter_path=adapter_path)
        return _hinglish_transcriber
