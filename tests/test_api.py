import sys
from pathlib import Path

# Ensure src is on Python path even when tests are executed directly
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from mediscribe.main import app

client = TestClient(app)
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_root_serves_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "MediScribe" in response.text
    assert "text/html" in response.headers.get("content-type", "")


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_presets_endpoint():
    response = client.get("/v1/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "cardiology" in preset_ids
    assert "code_mixed" in preset_ids


def test_sample_pdf_endpoint():
    response = client.get("/v1/sample-pdf")
    assert response.status_code == 200
    assert response.headers.get("content-type") == "application/pdf"
    assert len(response.content) > 0


def test_analyze_exposes_provenance_and_safety():
    response = client.post(
        "/v1/analyze",
        json={
            "encounter_id": "e1",
            "patient_id": "p1",
            "turns": [
                {
                    "turn_id": "a",
                    "speaker": "patient",
                    "text": "I have fever for 3 days and take warfarin 5 mg once a day.",
                },
                {
                    "turn_id": "b",
                    "speaker": "clinician",
                    "text": "Also taking aspirin 75 mg. Order a complete blood count.",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert any(
        e["type"] == "symptom" and e["provenance"]["turn_id"] == "a"
        for e in body["entities"]
    )
    assert any(
        a["category"] == "drug_interaction" and a["severity"] == "high"
        for a in body["safety_alerts"]
    )
    assert body["fhir_bundle"]["resourceType"] == "Bundle"


def test_analyze_text_endpoint():
    response = client.post(
        "/v1/analyze-text",
        data={
            "text": "Doctor: I prescribe amoxicillin 500 mg for the cough.\nPatient: Thank you."
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["entities"]) > 0
    assert len(body["turns"]) == 2


def test_analyze_file_endpoint_pdf():
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
        assert "_source" in body
        assert body["_source"]["filename"] == "sample.pdf"


def test_analyze_file_endpoint_txt():
    sample_txt = b"Doctor: Reviewing blood pressure.\nPatient: Taking lisinopril 10 mg."
    response = client.post(
        "/v1/analyze-file",
        files={"file": ("record.txt", sample_txt, "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["entities"]) > 0


def test_report_generation():
    analyze_res = client.post(
        "/v1/analyze-text",
        data={"text": "Doctor: Take paracetamol 500 mg for headache.\nPatient: Understood."},
    )
    assert analyze_res.status_code == 200
    report_res = client.post("/v1/report", json=analyze_res.json())
    assert report_res.status_code == 200
    assert "MediScribe AI" in report_res.text
    assert "Extracted Clinical Entities" in report_res.text


def test_validation_empty_text():
    response = client.post("/v1/analyze-text", data={"text": "   "})
    assert response.status_code == 400


if __name__ == "__main__":
    test_root_serves_frontend()
    test_health_endpoint()
    test_presets_endpoint()
    test_sample_pdf_endpoint()
    test_analyze_exposes_provenance_and_safety()
    test_analyze_text_endpoint()
    test_analyze_file_endpoint_pdf()
    test_analyze_file_endpoint_txt()
    test_report_generation()
    test_validation_empty_text()
    print("All 10 tests passed successfully!")
