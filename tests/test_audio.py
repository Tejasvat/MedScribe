import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is on Python path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from mediscribe.audio_service import (
    AudioJobManager,
    check_audio_dependencies,
    process_audio_file,
    validate_audio_file,
)
from mediscribe.main import app

client = TestClient(app)
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_audio_dependencies_endpoint():
    """Verify dependencies check endpoint returns structured dependency status."""
    response = client.get("/v1/audio/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert "has_whisperx" in data
    assert "has_ffmpeg" in data
    assert "has_hf_token" in data
    assert "required_gated_models" in data
    assert "pyannote/speaker-diarization-3.1" in data["required_gated_models"]
    assert "pyannote/segmentation-3.0" in data["required_gated_models"]


def test_audio_validation_valid():
    """Test validation of valid audio files."""
    dummy_wav = b"RIFF" + b"\x00" * 40
    res = validate_audio_file("consultation.wav", dummy_wav)
    assert res.is_valid is True
    assert res.error_message is None
    assert res.file_size_bytes == 44

    dummy_mp3 = b"ID3" + b"\x00" * 40
    res_mp3 = validate_audio_file("consultation.mp3", dummy_mp3)
    assert res_mp3.is_valid is True


def test_audio_validation_unsupported_extension():
    """Test rejection of unsupported file types."""
    res = validate_audio_file("recording.ogg", b"dummy")
    assert res.is_valid is False
    assert "Unsupported audio format" in res.error_message


def test_audio_validation_empty_file():
    """Test rejection of empty 0-byte audio."""
    res = validate_audio_file("empty.wav", b"")
    assert res.is_valid is False
    assert "empty" in res.error_message.lower()


def test_audio_validation_oversized_file():
    """Test rejection of files exceeding maximum allowed size."""
    res = validate_audio_file("large.wav", b"x" * 100, max_bytes=50)
    assert res.is_valid is False
    assert "exceeds maximum allowed size" in res.error_message


def test_audio_upload_rejection_for_bad_format():
    """Test that POST /v1/audio/upload returns HTTP 400 for unsupported formats."""
    response = client.post(
        "/v1/audio/upload",
        files={"file": ("recording.flac", b"FLACdummy", "audio/flac")},
    )
    assert response.status_code == 400
    assert "Unsupported audio format" in response.json()["detail"]


def test_audio_upload_rejection_for_empty_file():
    """Test that POST /v1/audio/upload returns HTTP 400 for empty files."""
    response = client.post(
        "/v1/audio/upload",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_audio_upload_accepted():
    """Test successful audio upload queuing background processing."""
    dummy_wav = b"RIFF" + b"\x00" * 100
    response = client.post(
        "/v1/audio/upload",
        files={"file": ("test_consultation.wav", dummy_wav, "audio/wav")},
    )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    assert body["filename"] == "test_consultation.wav"

    # Poll status endpoint
    job_id = body["job_id"]
    status_res = client.get(f"/v1/audio/status/{job_id}")
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["job_id"] == job_id
    assert status_body["status"] in ("queued", "transcribing", "diarizing", "completed", "failed")


def test_audio_status_not_found():
    """Test polling an unknown job_id returns 404."""
    response = client.get("/v1/audio/status/aud-unknown-999")
    assert response.status_code == 404


def test_audio_job_manager_cleanup():
    """Test job manager TTL expiration cleanup."""
    import time
    mgr = AudioJobManager(ttl_seconds=0)  # instant expiration
    job = mgr.create_job("test.wav")
    assert mgr.get_job(job.job_id) is not None
    time.sleep(0.01)
    # Creating a new job triggers cleanup of expired jobs
    job2 = mgr.create_job("test2.wav")
    # Old job should be expired and removed
    assert mgr.get_job(job.job_id) is None
    assert mgr.get_job(job2.job_id) is not None



def test_audio_processing_diarization_fallback_handling():
    """Test scenario where transcription succeeds but diarization fails or lacks HF_TOKEN."""
    from mediscribe.audio_service import job_manager

    test_job = job_manager.create_job("consultation.wav")

    # Simulate WhisperX mock
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 4.5, "text": "Good morning Mr. Kumar. What brings you in today?"},
            {"start": 5.0, "end": 10.0, "text": "I have had fever and cough for three days."},
        ],
    }

    with patch.dict("sys.modules", {"whisperx": MagicMock()}):
        import whisperx
        whisperx.load_audio.return_value = [0.0] * 16000
        whisperx.load_model.return_value = mock_model
        # Simulate check_audio_dependencies having ffmpeg and whisperx
        with patch("mediscribe.audio_service.check_audio_dependencies") as mock_deps:
            mock_deps.return_value = {
                "has_ffmpeg": True,
                "has_whisperx": True,
                "has_torch": True,
                "has_hf_token": False,
                "required_gated_models": [],
            }
            with patch("mediscribe.audio_service.get_whisperx_model", return_value=mock_model):
                with patch.dict("os.environ", {"HF_TOKEN": ""}):
                    process_audio_file("fake_path.wav", job_id=test_job.job_id)

    updated_job = job_manager.get_job(test_job.job_id)
    assert updated_job.status == "completed"
    assert len(updated_job.segments) == 2
    # Verify diarization warning is clearly recorded explaining HF_TOKEN is required
    assert updated_job.diarization_warning is not None
    assert "HF_TOKEN" in updated_job.diarization_warning
    assert "pyannote/speaker-diarization-3.1" in updated_job.diarization_warning


def test_audio_analyze_with_reviewed_transcript_and_speaker_roles():
    """Verify that only the user-reviewed and edited transcript is passed to the clinical NER pipeline."""
    payload = {
        "encounter_id": "enc-test-audio-01",
        "patient_id": "pat-01",
        "patient_name": "Rahul Verma",
        "physician_name": "Dr. Sarah Jenkins",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker_id": "SPEAKER_00",
                "role": "doctor",
                "start_sec": 0.0,
                "end_sec": 4.5,
                "text": "Good morning Mr. Rahul Verma, what symptoms are bothering you?",
            },
            {
                "segment_id": "seg_002",
                "speaker_id": "SPEAKER_01",
                "role": "patient",
                "start_sec": 5.0,
                "end_sec": 12.0,
                "text": "I have had fever, severe cough, and chest tightness for three days. I took Paracetamol 500 mg yesterday.",
            },
            {
                "segment_id": "seg_003",
                "speaker_id": "SPEAKER_00",
                "role": "doctor",
                "start_sec": 13.0,
                "end_sec": 20.0,
                "text": "I will prescribe amoxicillin 500 mg three times daily for 7 days. Also, order a complete blood count.",
            },
        ],
        "speaker_roles": {
            "SPEAKER_00": "doctor",
            "SPEAKER_01": "patient",
        },
    }

    response = client.post("/v1/audio/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()

    # 1. Check patient & physician identity
    assert body["patient_name"] == "Rahul Verma"
    assert body["physician_name"] == "Dr. Sarah Jenkins"

    # 2. Check entities extracted
    entity_texts = [e["text"].lower() for e in body["entities"]]
    assert "fever" in entity_texts
    assert "cough" in entity_texts
    assert "chest tightness" in entity_texts
    assert "amoxicillin" in entity_texts

    # 3. Check medication status distinction
    med_statuses = {m["normalized_name"] or m["mention"].lower(): m["status"] for m in body["medications"]}
    assert "amoxicillin" in med_statuses
    assert med_statuses["amoxicillin"] == "prescribed"

    # 4. Check SOAP note content generated from reviewed transcript
    soap = body["soap_note"]
    assert any("Fever" in s or "Cough" in s for s in soap["subjective"])
    assert any("Amoxicillin" in p for p in soap["plan"])
    assert any("complete blood count" in o.lower() for o in soap["objective"])

    # 5. Check FHIR Bundle
    fhir = body["fhir_bundle"]
    assert fhir["resourceType"] == "Bundle"
    res_types = [e["resource"]["resourceType"] for e in fhir["entry"]]
    assert "Patient" in res_types
    assert "Practitioner" in res_types
    assert "Encounter" in res_types
    assert "Condition" in res_types
    assert "MedicationRequest" in res_types


def test_audio_analyze_uses_edited_corrections_not_unreviewed():
    """Verify that if the user corrects an error in the transcript (e.g. changes a misheard drug name),
    the report generation strictly reflects the edited text.
    """
    payload = {
        "encounter_id": "enc-test-audio-edited",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker_id": "SPEAKER_00",
                "role": "doctor",
                "start_sec": 0.0,
                "end_sec": 5.0,
                # User edited transcript to Azithromycin instead of a misheard word
                "text": "I will prescribe azithromycin 250 mg once daily for 5 days.",
            },
        ],
        "speaker_roles": {"SPEAKER_00": "doctor"},
    }

    response = client.post("/v1/audio/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()

    # The report should have azithromycin, reflecting the user's edited transcript
    med_names = [m["normalized_name"] or m["mention"].lower() for m in body["medications"]]
    assert "azithromycin" in med_names
    assert any("Azithromycin" in p for p in body["soap_note"]["plan"])


def test_existing_pdf_workflow_still_functional():
    """Ensure existing PDF workflow is completely intact and unaffected."""
    sample_pdf_path = EXAMPLES_DIR / "sample_clinical_record.pdf"
    if sample_pdf_path.exists():
        with open(sample_pdf_path, "rb") as f:
            response = client.post(
                "/v1/analyze-file",
                files={"file": ("sample.pdf", f.read(), "application/pdf")},
            )
        assert response.status_code == 200
        body = response.json()
        assert len(body["entities"]) > 0
        assert body["fhir_bundle"]["resourceType"] == "Bundle"
        assert body["_source"]["type"] == "pdf"


def test_hinglish_adapter_availability():
    """Verify Hinglish PolyWhisper adapter is recognized."""
    from mediscribe.polywhisper import get_hinglish_transcriber
    transcriber = get_hinglish_transcriber()
    assert transcriber.is_available() is True
    assert transcriber.adapter_path.name in ("hinglish_adapter.zip", "hinglish_adapter.pt")

