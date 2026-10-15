from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .clinical import draft_soap, normalize_medications, safety_alerts
from .extraction import get_extractor
from .fhir import build_bundle
from .pdf_parser import (
    ParsedDocument,
    extract_text_from_pdf,
    extract_text_from_txt,
    segment_into_turns,
)
from .report import generate_html_report
from .schemas import AnalyzeRequest, AnalyzeResponse, TranscriptTurn

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

# Serve the frontend static files
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
EXAMPLES_DIR = BASE_DIR / "examples"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    """Serve the MediScribe AI frontend."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>MediScribe AI API</h1>"
        '<p>Frontend not found. Visit <a href="/docs">/docs</a> for API docs.</p>'
    )


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
    entities = extractor.extract(request.turns)
    medications = normalize_medications(entities)
    return AnalyzeResponse(
        encounter_id=request.encounter_id,
        turns=request.turns,
        entities=entities,
        medications=medications,
        safety_alerts=safety_alerts(medications),
        soap_note=draft_soap(request.turns, entities),
        fhir_bundle=build_bundle(
            request.encounter_id, request.patient_id, entities, medications
        ),
    )


@app.post("/v1/analyze-text")
def analyze_text(
    text: str = Form(...),
    encounter_id: str = Form(default=""),
    patient_id: str = Form(default=""),
) -> JSONResponse:
    """Analyze raw text input (pasted or typed)."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text input is empty.")

    enc_id = encounter_id or f"enc-{uuid.uuid4().hex[:8]}"
    pat_id = patient_id or None

    turns_data = segment_into_turns(text.strip())
    turns = [TranscriptTurn(**t) for t in turns_data]

    entities = extractor.extract(turns)
    medications = normalize_medications(entities)

    response = AnalyzeResponse(
        encounter_id=enc_id,
        turns=turns,
        entities=entities,
        medications=medications,
        safety_alerts=safety_alerts(medications),
        soap_note=draft_soap(turns, entities),
        fhir_bundle=build_bundle(enc_id, pat_id, entities, medications),
    )

    return JSONResponse(content=json.loads(response.model_dump_json()))


@app.post("/v1/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    encounter_id: str = Form(default=""),
    patient_id: str = Form(default=""),
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

    entities = extractor.extract(turns)
    medications = normalize_medications(entities)

    response = AnalyzeResponse(
        encounter_id=enc_id,
        turns=turns,
        entities=entities,
        medications=medications,
        safety_alerts=safety_alerts(medications),
        soap_note=draft_soap(turns, entities),
        fhir_bundle=build_bundle(enc_id, pat_id, entities, medications),
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
