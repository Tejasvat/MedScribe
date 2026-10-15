# MediScribe AI — Assistive Clinical Documentation & NER Service

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-10%20Passing-brightgreen.svg)]()
[![FHIR](https://img.shields.io/badge/FHIR-R4%20Compliant-orange.svg)](https://hl7.org/fhir/R4/)

**MediScribe AI** is an auditable, real-time assistive clinical documentation service that operates post-transcription. It transforms diarized clinical consultation dialogues or uploaded medical records (PDF/TXT) into structured, safety-checked, EHR-ready clinical documentation.

The service incorporates a built-in interactive web application, an automated RxNorm medication normalizer, a Drug-Drug Interaction (DDI) & duplicate therapy safety engine, automated SOAP note drafting, and FHIR R4 Bundle generation.

> **Important Clinical Notice**: This service is an assistive drafting and review tool. It does not diagnose, prescribe, or unilaterally modify medications. All outputs require review and approval by a licensed clinician before inclusion in a patient's medical record.

---

## Key Features

1. **Medical Named Entity Recognition (NER)**
   - Extracts 7 distinct clinical entity types: `symptom`, `drug`, `dosage`, `frequency`, `duration`, `test`, and `adverse_event`.
   - Character-level provenance tracking: turn ID, exact character offsets (`start_char`, `end_char`), and verbatim source snippet.
   - Dual-engine support: High-throughput **RuleBasedExtractor** (zero-download default) and plug-and-play **TransformersExtractor** for fine-tuned BioBERT/ClinicalBERT models.

2. **Medication Normalization & RxNorm Mapping**
   - Resolves clinical brand names and mentions to canonical generic names and official RxCUI identifiers (e.g., Tylenol -> Acetaminophen RxCUI `161`, Coumadin -> Warfarin RxCUI `11289`, Lipitor -> Atorvastatin RxCUI `83367`).

3. **Clinical Safety & Drug Interaction Engine**
   - High and moderate severity drug-drug interaction (DDI) rules aligned with DDInter and DrugBank (e.g., Warfarin + Aspirin bleeding risk, Lisinopril + Spironolactone hyperkalemia, SSRI + NSAID mucosal bleed warnings).
   - Duplicate therapy alerts flags repeated medications across the encounter.

4. **Conservative SOAP Note Generation**
   - Automatically drafts **S**ubjective, **O**bjective, **A**ssessment, and **P**lan clinical sections from conversation turns and confirmed entities.

5. **Interoperable FHIR R4 Export**
   - Outputs valid HL7 FHIR R4 Bundles containing `Condition`, `MedicationStatement`, and `ServiceRequest` resources mapped with clinical provenance extensions.

7. **Audio Consultation Ingestion (WhisperX & Speaker Diarization)**
   - Upload MP3/WAV audio recordings up to 50 MB with asynchronous background processing.
   - WhisperX with `small` speech-recognition model, CPU execution, and INT8 quantization for on-device clinical transcription.
   - Integrated speaker diarization powered by `pyannote.audio` with timestamp alignment.
   - Interactive human-in-the-loop transcript review interface with editable segments and doctor/patient role assignment.
   - Feeds directly into the existing clinical NER, medication normalizer, safety alert, SOAP, and FHIR pipeline without duplicate systems.

---

## Project Structure

```text
NER/
├── src/
│   └── mediscribe/
│       ├── __init__.py         # Package root
│       ├── audio_service.py    # WhisperX transcription, diarization & job manager
│       ├── clinical.py         # RxNorm normalization, DDI safety alerts, SOAP generator
│       ├── extraction.py       # RuleBasedExtractor and TransformersExtractor
│       ├── fhir.py             # HL7 FHIR R4 Bundle builder
│       ├── main.py             # FastAPI application and route handlers
│       ├── pdf_parser.py       # PDF/TXT extraction and speaker turn segmentation
│       ├── report.py           # HTML/PDF clinical report template engine
│       └── schemas.py          # Pydantic v2 schemas and validation models
├── frontend/                   # Web application served directly by FastAPI (Lumina Health UI)
│   ├── index.html              # Modern, responsive UI with Audio Review & Intake tabs
│   ├── styles.css              # Custom styling with accessible clinical color tokens
│   └── app.js                  # Frontend state management, polling & review controller
├── tests/
│   ├── test_api.py             # Existing FastAPI endpoint test suite
│   ├── test_audio.py           # Audio validation, status, review & pipeline tests
│   └── test_regression.py      # Core clinical NER & safety regression tests
├── examples/
│   ├── request.json            # Sample JSON payload for /v1/analyze
│   └── sample_clinical_record.pdf # Pre-generated clinical record for upload testing
├── .env.example                # Template for HF_TOKEN & WhisperX execution settings
├── requirements.txt            # Core & audio consultation runtime dependencies
└── README.md                   # Project documentation
```


---

## Getting Started

### Prerequisites

- **Python 3.11+** installed
- Windows PowerShell, macOS Terminal, or Linux Shell

---

### Installation

1. **Clone or navigate into the repository**:
   ```bash
   cd c:\Users\tejas\Documents\NER
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install the core dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   *(Alternatively, install in editable mode: `pip install -e .`)*

---

### Running the Application

Start the local server using Uvicorn:

```powershell
uvicorn mediscribe.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Interactive Web Interface**: Open your browser to [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger / OpenAPI Documentation**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc Docs**: Open [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

### Audio Consultation Prerequisites (WhisperX & Pyannote)

1. **System Dependency: FFmpeg**
   WhisperX relies on FFmpeg to decode audio streams:
   - **Windows (winget)**:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **Windows (Chocolatey)**:
     ```powershell
     choco install ffmpeg
     ```
   - **macOS (Homebrew)**:
     ```bash
     brew install ffmpeg
     ```
   - **Ubuntu/Debian**:
     ```bash
     sudo apt-get install -y ffmpeg
     ```

2. **Hugging Face Model Access (for Speaker Diarization)**
   Pyannote diarization uses gated models that require user agreement on Hugging Face:
   - Create or log into your [Hugging Face account](https://huggingface.co/).
   - Visit and accept the conditions for:
     1. [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
     2. [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
   - Generate a User Access Token (with `Read` permission) at [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
   - Create your local `.env` file (never commit this file):
     ```powershell
     Copy-Item .env.example .env
     ```
   - Set `HF_TOKEN=hf_...` in `.env`.

---

### Running Tests

Execute the automated test suite with `pytest`:

```powershell
pytest
```

All 37 test cases verify:
- Audio file validation (MP3/WAV format, 50 MB limit, safe unique names)
- Audio processing lifecycle, polling, and background job manager
- Fallback handling when transcription succeeds but diarization lacks HF_TOKEN
- Review screen role mapping (Doctor, Patient) and segment editing
- Direct integration into clinical NER, medication normalization, safety alerts, SOAP, and FHIR Bundle
- Verification that edited transcript corrections override unreviewed transcripts
- Preservation of existing PDF/TXT and free-text analysis endpoints

---

## API Reference

### 1. `GET /health`
Returns service operational health.
```json
{
  "status": "ok",
  "service": "MediScribe AI",
  "version": "1.0.0"
}
```

### 2. `GET /v1/audio/dependencies`
Inspects environment for WhisperX, Pyannote, PyTorch, FFmpeg, and HF token status.

### 3. `POST /v1/audio/upload`
Uploads an MP3 or WAV file (up to 50 MB) for asynchronous WhisperX background transcription and speaker diarization.
Returns HTTP 202 with `job_id`:
```json
{
  "job_id": "aud-1a2b3c4d5e6f",
  "filename": "consultation.wav",
  "status": "queued",
  "progress": 5,
  "message": "Audio file accepted for background processing."
}
```

### 4. `GET /v1/audio/status/{job_id}`
Polls progress, status (`transcribing`, `diarizing`, `completed`, `failed`), detected speakers, transcript segments, and any diarization warnings.

### 5. `POST /v1/audio/analyze`
Executes clinical NER, medication normalization, safety alerts, SOAP note drafting, and FHIR Bundle generation **only on the user-reviewed transcript segments and assigned speaker roles**.

### 6. `GET /v1/presets`
Returns predefined clinical scenario dialogues (Cardiology, Code-Mixed EN-TA, Polypharmacy, Outpatient) for immediate testing.

### 7. `GET /v1/sample-pdf`
Downloads a sample clinical record PDF for file upload testing.

### 8. `POST /v1/analyze-text`
Analyzes free-text consultations. Form fields:
- `text` (string, required): Raw dialogue or consultation text.
- `encounter_id` (string, optional): Unique encounter ID.
- `patient_id` (string, optional): Associated patient ID.

### 9. `POST /v1/analyze-file`
Processes an uploaded file (`.pdf` or `.txt`). Form fields:
- `file` (binary, required): Clinical document.
- `encounter_id` (string, optional)
- `patient_id` (string, optional)


### 10. `POST /v1/analyze`
JSON endpoint accepting pre-segmented diarized transcript turns.
```json
{
  "encounter_id": "enc-101",
  "patient_id": "pat-202",
  "turns": [
    {
      "turn_id": "t1",
      "speaker": "patient",
      "text": "I have had fever for 3 days and take warfarin 5 mg daily."
    },
    {
      "turn_id": "t2",
      "speaker": "clinician",
      "text": "I am prescribing aspirin 75 mg and ordering a complete blood count."
    }
  ]
}
```

### 11. `POST /v1/report`
Accepts the analysis response JSON payload and returns a styled, print-ready HTML clinical report with medication tables, safety warning cards, and SOAP summaries.


---

## Using a Production Transformer Model

The service defaults to the deterministic `RuleBasedExtractor`, allowing the project to run immediately without downloading gigabyte-sized weight files.

To attach a fine-tuned Hugging Face or local transformer model (e.g., BioBERT, ClinicalBERT):

1. Install the ML extras:
   ```powershell
   pip install -e ".[ml]"
   # Or directly:
   pip install torch transformers
   ```

2. Set the environment variable:
   - **PowerShell**:
     ```powershell
     $env:MEDISCRIBE_NER_MODEL = "d4data/biomedical-ner-all"
     ```
   - **Linux / macOS**:
     ```bash
     export MEDISCRIBE_NER_MODEL="d4data/biomedical-ner-all"
     ```

3. Restart the Uvicorn server. The service will load the transformer pipeline while keeping all downstream clinical logic (RxNorm mapping, DDI safety alerts, FHIR generation, SOAP drafting) completely intact.

---

## Docker Deployment

Build and run the containerized service:

```bash
# Build the Docker image
docker build -t mediscribe-ai .

# Run the container on port 8000
docker run -d -p 8000:8000 --name mediscribe-service mediscribe-ai
```

The container runs as an unprivileged user (`appuser`) and exposes the web UI and API at `http://localhost:8000/`.

---

## Security & Deployment Best Practices

- **Zero Outbound Data Transmission**: The service does not make unsolicited outbound internet requests; all terminology lookups (RxNorm) and safety rules are evaluated locally.
- **TLS & Authentication**: Always deploy behind a TLS reverse proxy (e.g., NGINX, Cloudflare, Traefik) with appropriate organizational OAuth2/mTLS authentication.
- **Audit Trails**: Maintain encrypted persistence only within your organization's HIPAA/GDPR-compliant database.
