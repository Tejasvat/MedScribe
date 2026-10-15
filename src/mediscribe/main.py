from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from pathlib import Path

# Load .env before any other local imports so environment variables
# (FFMPEG_PATH, HF_TOKEN, WHISPER_MODEL, etc.) are available immediately.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on system environment

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .clinical import (
    draft_soap,
    extract_allergies,
    extract_investigations,
    normalize_medications,
    safety_alerts,
)
from .extraction import extract_identities, get_extractor
from .fhir import build_bundle
from .pdf_parser import (
    ParsedDocument,
    extract_text_from_pdf,
    extract_text_from_txt,
    segment_into_turns,
)
from .audio_service import (
    DEFAULT_MAX_AUDIO_BYTES,
    check_audio_dependencies,
    job_manager,
    process_audio_file,
    validate_audio_file,
)
from .report import generate_html_report
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AudioAnalyzeRequest,
    AudioStatusResponse,
    AudioTranscriptSegment,
    Speaker,
    TranscriptTurn,
)


def run_pipeline(
    turns: list[TranscriptTurn],
    enc_id: str,
    pat_id: str | None = None,
    patient_name: str = "",
    physician_name: str = "",
) -> AnalyzeResponse:
    """Execute the core clinical NER, medication normalization, safety, SOAP, and FHIR pipeline."""
    extracted_patient, extracted_age, extracted_physician = extract_identities(turns)
    pat_name = patient_name.strip() or extracted_patient
    phys_name = physician_name.strip() or extracted_physician

    entities = extractor.extract(turns)
    medications = normalize_medications(entities, turns)
    allergies = extract_allergies(turns, entities)
    investigations = extract_investigations(turns, entities)
    alerts = safety_alerts(medications, allergies)
    soap = draft_soap(
        turns,
        entities,
        medications=medications,
        allergies=allergies,
        investigations=investigations,
        patient_name=pat_name,
        patient_age=extracted_age,
        physician_name=phys_name,
    )
    bundle = build_bundle(
        enc_id,
        pat_id,
        entities,
        medications,
        allergies=allergies,
        investigations=investigations,
        patient_name=pat_name,
        physician_name=phys_name,
    )

    return AnalyzeResponse(
        encounter_id=enc_id,
        patient_id=pat_id,
        patient_name=pat_name,
        patient_age=extracted_age,
        physician_name=phys_name,
        turns=turns,
        entities=entities,
        medications=medications,
        investigations=investigations,
        allergies=allergies,
        safety_alerts=alerts,
        soap_note=soap,
        fhir_bundle=bundle,
    )


app = FastAPI(
    title="MediScribe AI",
    version="1.0.0",
    description="Real-Time Assistive Clinical Documentation & Medical Named Entity Recognition System.",
)

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = get_extractor()

# Robust frontend and examples directory resolution across dev, pip install, and container environments
def _resolve_dir(dirname: str) -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent.parent / dirname,  # git repo root: src/mediscribe/../../dirname
        Path.cwd() / dirname,                                     # current working directory
        Path("/app") / dirname,                                   # standard docker container path
        Path(__file__).resolve().parent / dirname,                # packaged alongside mediscribe module
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = _resolve_dir("frontend")
EXAMPLES_DIR = _resolve_dir("examples")

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    """Serve the MediScribe AI frontend."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.is_file():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    
    # Fallback search if index.html is in any candidate directory
    for candidate in [Path.cwd() / "frontend" / "index.html", Path("/app/frontend/index.html")]:
        if candidate.is_file():
            return HTMLResponse(content=candidate.read_text(encoding="utf-8"))

    return HTMLResponse(
        content=f"<h1>MediScribe AI API</h1><p>Frontend not found at {FRONTEND_DIR}. Visit <a href='/docs'>/docs</a> for API docs.</p>"
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return inline SVG favicon."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36"><rect width="36" height="36" rx="10" fill="#18191c"/><path d="M18 8v20M8 18h20" stroke="#d2f84b" stroke-width="3.5" stroke-linecap="round"/><circle cx="18" cy="18" r="6" stroke="#b6b0ee" stroke-width="2" fill="none"/></svg>'
    return HTMLResponse(content=svg, media_type="image/svg+xml")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "MediScribe AI", "version": "1.0.0"}


@app.get("/v1/sample-pdf")
def get_sample_pdf() -> FileResponse:
    """Download a pre-generated clinical record PDF for testing file upload."""
    sample_pdf_path = EXAMPLES_DIR / "sample_clinical_record.pdf"
    if not sample_pdf_path.exists():
        raise HTTPException(status_code=404, detail="Sample PDF not found.")
    return FileResponse(
        path=str(sample_pdf_path),
        filename="sample_clinical_record.pdf",
        media_type="application/pdf",
    )


@app.get("/v1/presets")
def get_presets() -> JSONResponse:
    """Return clinical dialogue presets matching the research datasets and clinical scenarios."""
    presets = [
        {
            "id": "cardiology",
            "title": "Cardiology & Anticoagulant Risk",
            "badge": "High Safety Risk",
            "badge_class": "badge-danger",
            "description": "Patient on Warfarin prescribed Aspirin with reported dizziness, nausea, and order for CBC & ECG.",
            "text": (
                "Patient: Doctor, I have had high fever, severe cough, and chest tightness for three days. "
                "I took Paracetamol 500 mg twice daily, but it caused severe nausea and vomiting.\n\n"
                "Doctor: I understand. Let us discontinue the paracetamol for now. Have you had any chills or shortness of breath?\n\n"
                "Patient: Yes, breathlessness especially when climbing stairs. Also, I am currently taking warfarin 5 mg once daily for atrial fibrillation.\n\n"
                "Doctor: Noted. Because of your cardiac history, we cannot combine ibuprofen with warfarin due to severe bleeding risk. "
                "I will order a complete blood count, troponin test, and an electrocardiogram (ECG). "
                "I will also prescribe amoxicillin 500 mg three times daily for 7 days to cover bacterial pneumonia.\n\n"
                "Patient: I also take lisinopril 10 mg daily for hypertension. Should I continue it?\n\n"
                "Doctor: Yes, continue lisinopril 10 mg once daily. Let us also schedule a chest X-ray this afternoon. "
                "If you experience dizziness or worsening fatigue, call our emergency line immediately."
            ),
        },
        {
            "id": "code_mixed",
            "title": "Code-Mixed English–Tamil Consultation",
            "badge": "Novelty: Feature A",
            "badge_class": "badge-novelty",
            "description": "Realistic code-switched consultation speech demonstrating cross-lingual NER extraction.",
            "text": (
                "Patient: Doctor, enakku severe fever and dry cough irukku since Monday. "
                "I took Paracetamol 650 mg twice daily after food, but headache innum korayala.\n\n"
                "Doctor: Saringa. Any chest pain or breathlessness irukka?\n\n"
                "Patient: Konjam tiredness and dizziness irukku doctor. Also stomach pain after taking tablet.\n\n"
                "Doctor: Alright, Paracetamol stop pannunga. I will prescribe Azithromycin 500 mg once daily for 5 days. "
                "Also order complete blood count and blood glucose test to rule out infection. "
                "Take Pantoprazole 40 mg before breakfast for gastric protection.\n\n"
                "Patient: Thank you doctor, I will take the blood test today itself."
            ),
        },
        {
            "id": "polypharmacy",
            "title": "Polypharmacy & Renal Interaction",
            "badge": "Drug Interaction",
            "badge_class": "badge-warning",
            "description": "Metformin, Lisinopril, Spironolactone, and NSAID co-prescription checks.",
            "text": (
                "Doctor: Good morning Mr. Sharma, let us review your current medications for your type 2 diabetes and hypertension.\n\n"
                "Patient: Good morning doctor. I am taking metformin 1000 mg twice daily and lisinopril 20 mg once daily. "
                "Lately I have had swollen ankles and knee joint pain for two weeks.\n\n"
                "Doctor: For the joint swelling, I notice someone suggested ibuprofen 400 mg. We must avoid combining ibuprofen with lisinopril "
                "as that severely impairs renal perfusion. I also want to check your potassium and serum creatinine.\n\n"
                "Patient: My previous doctor also mentioned adding spironolactone 25 mg for fluid retention.\n\n"
                "Doctor: Spironolactone combined with lisinopril carries a critical risk of life-threatening hyperkalemia. "
                "We will defer spironolactone until after the basic metabolic panel results are in. "
                "Continue metformin and lisinopril, order BMP and HbA1c, and use paracetamol for mild analgesia."
            ),
        },
        {
            "id": "outpatient",
            "title": "General Practice Outpatient Visit",
            "badge": "Standard Care",
            "badge_class": "badge-info",
            "description": "Acute pharyngitis with fever, amoxicillin allergy check, and symptom timeline.",
            "text": (
                "Patient: Hello doctor, I have a sore throat, runny nose, and moderate fever that started four days ago. "
                "I have also noticed difficulty swallowing and severe fatigue.\n\n"
                "Doctor: Let me examine your pharynx. Tonsils appear erythematous. Have you taken any over-the-counter medicine?\n\n"
                "Patient: I took ibuprofen 200 mg yesterday, but it did not help much. I am allergic to penicillin and amoxicillin — they give me hives and skin rash.\n\n"
                "Doctor: Thank you for alerting me to the penicillin allergy. I will document the allergic reaction. "
                "Instead of beta-lactams, I will prescribe azithromycin 250 mg once daily for 5 days. "
                "Let us also do a rapid strep test and throat culture. Drink plenty of warm fluids."
            ),
        },
    ]
    return JSONResponse(content=presets)


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Original JSON-based analysis endpoint."""
    patient_name, patient_age, physician_name = extract_identities(request.turns)
    pat_name = request.patient_name or patient_name
    phys_name = request.physician_name or physician_name

    entities = extractor.extract(request.turns)
    medications = normalize_medications(entities, request.turns)
    allergies = extract_allergies(request.turns, entities)
    investigations = extract_investigations(request.turns, entities)
    alerts = safety_alerts(medications, allergies)
    soap = draft_soap(
        request.turns,
        entities,
        medications=medications,
        allergies=allergies,
        investigations=investigations,
        patient_name=pat_name,
        patient_age=patient_age,
        physician_name=phys_name,
    )
    bundle = build_bundle(
        request.encounter_id,
        request.patient_id,
        entities,
        medications,
        allergies=allergies,
        investigations=investigations,
        patient_name=pat_name,
        physician_name=phys_name,
    )
    return AnalyzeResponse(
        encounter_id=request.encounter_id,
        patient_id=request.patient_id,
        patient_name=pat_name,
        patient_age=patient_age,
        physician_name=phys_name,
        turns=request.turns,
        entities=entities,
        medications=medications,
        investigations=investigations,
        allergies=allergies,
        safety_alerts=alerts,
        soap_note=soap,
        fhir_bundle=bundle,
    )


@app.post("/v1/analyze-text")
def analyze_text(
    text: str = Form(...),
    encounter_id: str = Form(default=""),
    patient_id: str = Form(default=""),
    patient_name: str = Form(default=""),
    physician_name: str = Form(default=""),
) -> JSONResponse:
    """Analyze raw text input (pasted or typed)."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text input is empty.")

    enc_id = encounter_id or f"enc-{uuid.uuid4().hex[:8]}"
    pat_id = patient_id or None

    turns_data = segment_into_turns(text.strip())
    turns = [TranscriptTurn(**t) for t in turns_data]

    response = run_pipeline(
        turns=turns,
        enc_id=enc_id,
        pat_id=pat_id,
        patient_name=patient_name,
        physician_name=physician_name,
    )

    return JSONResponse(content=json.loads(response.model_dump_json()))


@app.post("/v1/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    encounter_id: str = Form(default=""),
    patient_id: str = Form(default=""),
    patient_name: str = Form(default=""),
    physician_name: str = Form(default=""),
) -> JSONResponse:
    """Analyze uploaded PDF or TXT file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    file_bytes = await file.read()
    ext = Path(file.filename).suffix.lower()

    try:
        if ext == ".pdf":
            parsed = extract_text_from_pdf(file_bytes)
        elif ext in (".txt", ".text", ".csv", ".md"):
            parsed = extract_text_from_txt(file_bytes)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Please upload PDF or TXT.",
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    enc_id = encounter_id or f"enc-{uuid.uuid4().hex[:8]}"
    pat_id = patient_id or None

    turns_data = segment_into_turns(parsed.raw_text)
    turns = [TranscriptTurn(**t) for t in turns_data]

    response = run_pipeline(
        turns=turns,
        enc_id=enc_id,
        pat_id=pat_id,
        patient_name=patient_name,
        physician_name=physician_name,
    )

    result = json.loads(response.model_dump_json())
    result["_source"] = {
        "filename": file.filename,
        "type": parsed.source_type,
        "pages": parsed.page_count,
        "raw_text_preview": parsed.raw_text[:500],
    }

    return JSONResponse(content=result)


@app.post("/v1/report")
def generate_report(data: dict) -> HTMLResponse:
    """Generate a downloadable HTML report from analysis results."""
    report_html = generate_html_report(data)
    return HTMLResponse(content=report_html)


# =========================================================================
# 🎙️ AUDIO CONSULTATION ENDPOINTS (WhisperX & Speaker Diarization)
# =========================================================================

@app.get("/v1/audio/dependencies")
def get_audio_dependencies() -> dict[str, Any]:
    """Inspect environment for audio dependencies, models, and HF token."""
    return check_audio_dependencies()


@app.post("/v1/audio/upload")
async def upload_audio(
    file: UploadFile = File(...),
) -> JSONResponse:
    """Upload and validate an MP3 or WAV audio consultation file for asynchronous processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")

    file_bytes = await file.read()
    val = validate_audio_file(file.filename, file_bytes, max_bytes=DEFAULT_MAX_AUDIO_BYTES)
    if not val.is_valid:
        raise HTTPException(status_code=400, detail=val.error_message)

    # Save to temporary secure file
    suffix = val.file_extension
    temp_dir = Path(tempfile.gettempdir()) / "mediscribe_audio"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_audio_path = temp_dir / f"{uuid.uuid4().hex}{suffix}"
    temp_audio_path.write_bytes(file_bytes)

    # Create background job
    job = job_manager.create_job(filename=file.filename)

    # Launch background thread for transcription and diarization
    def run_worker() -> None:
        try:
            process_audio_file(str(temp_audio_path), job_id=job.job_id)
        finally:
            # Clean up temporary audio file after processing completes
            try:
                if temp_audio_path.exists():
                    temp_audio_path.unlink()
            except OSError:
                pass

    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job.job_id,
            "filename": file.filename,
            "status": "queued",
            "progress": 5,
            "message": "Audio file accepted for background processing.",
        },
    )


@app.get("/v1/audio/status/{job_id}", response_model=AudioStatusResponse)
def get_audio_status(job_id: str) -> JSONResponse:
    """Poll processing status, progress, and diarization output of an audio consultation."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Audio job not found.")

    return JSONResponse(
        content={
            "job_id": job.job_id,
            "filename": job.filename,
            "status": job.status,
            "progress": job.progress,
            "segments": job.segments,
            "speakers": job.speakers,
            "error_message": job.error_message,
            "diarization_warning": job.diarization_warning,
            "duration_sec": job.duration_sec,
        }
    )


@app.post("/v1/audio/analyze")
def analyze_reviewed_audio_transcript(
    payload: AudioAnalyzeRequest,
) -> JSONResponse:
    """Analyze the user-reviewed and edited audio transcript segments.

    Only the reviewed transcript and assigned roles (Doctor, Patient) are passed
    into the clinical NER, medication extraction, safety alert, SOAP, and FHIR pipeline.
    """
    if not payload.segments:
        raise HTTPException(status_code=400, detail="No transcript segments provided.")

    turns: list[TranscriptTurn] = []
    for idx, seg in enumerate(payload.segments):
        # Determine speaker role: explicitly given on segment, or mapped from speaker_id
        role = seg.role.lower().strip()
        if role in ("unknown", ""):
            role = payload.speaker_roles.get(seg.speaker_id, "unknown").lower().strip()

        if role in ("doctor", "clinician", "physician"):
            turn_speaker = Speaker.CLINICIAN
        elif role in ("patient", "pt"):
            turn_speaker = Speaker.PATIENT
        else:
            turn_speaker = Speaker.UNKNOWN

        start_ms = int(seg.start_sec * 1000) if seg.start_sec is not None else None
        end_ms = int(seg.end_sec * 1000) if seg.end_sec is not None else None

        turns.append(
            TranscriptTurn(
                turn_id=seg.segment_id or f"t{idx + 1}",
                speaker=turn_speaker,
                text=seg.text.strip(),
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )

    response = run_pipeline(
        turns=turns,
        enc_id=payload.encounter_id,
        pat_id=payload.patient_id,
        patient_name=payload.patient_name or "",
        physician_name=payload.physician_name or "",
    )

    result = json.loads(response.model_dump_json())
    result["_source"] = {
        "type": "audio",
        "segment_count": len(payload.segments),
        "speakers": list(payload.speaker_roles.keys()),
    }
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("mediscribe.main:app", host="0.0.0.0", port=port)


