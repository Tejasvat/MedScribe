from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from mediscribe.main import app
from mediscribe.schemas import (
    EntityType,
    InvestigationStatus,
    MedicationStatus,
)

client = TestClient(app)

SAMPLE_TRANSCRIPT = """
Doctor: Hello, I am Dr. Meera Sharma. You must be Rahul Verma, age 29. What brings you to the clinic today?
Patient: Hello Dr. Sharma. For the past three days, I have had a severe cough, sore throat, fever, wheezing, extreme fatigue, headache, and mild breathlessness.
Doctor: Thank you for sharing that. Do you have any chest pain or confusion?
Patient: No, I have no chest pain or confusion at all. I do have a past medical history of mild asthma.
Doctor: Understood. What existing medications are you currently taking?
Patient: I am currently taking salbutamol inhaler as needed and cetirizine 10 mg daily for my allergies. Yesterday, I also previously took paracetamol 500 mg for the fever, but it only helped slightly.
Doctor: Noted. Do you have any known drug allergies or adverse reactions?
Patient: Yes, I have a penicillin allergy. I previously developed a severe skin rash from amoxicillin several years ago.
Doctor: Thank you for alerting me to the penicillin allergy. We must strictly avoid amoxicillin and all penicillin-related drugs. I considered azithromycin, but azithromycin is not prescribed since this presentation appears viral. We also considered budesonide, but we will not prescribe budesonide at this stage.
Doctor: For symptomatic relief, I recommend paracetamol 500 mg every 6 hours as needed for your fever and headache. Please continue your current salbutamol and cetirizine. Let us discuss a COVID-19 antigen test to rule out viral infection. We will also consider a chest X-ray if your breathlessness worsens, but a chest X-ray is not ordered today.
"""


def get_analysis_result():
    res = client.post(
        "/v1/analyze-text",
        data={"text": SAMPLE_TRANSCRIPT.strip()},
    )
    assert res.status_code == 200
    return res.json()


def test_regression_patient_and_physician_identities():
    data = get_analysis_result()
    # Physician and patient names must be extracted from transcript
    assert data["physician_name"] == "Dr. Meera Sharma"
    assert data["patient_name"] == "Rahul Verma"
    assert data["patient_age"] == 29
    # Must maintain separate patient_id and encounter_id
    assert data["encounter_id"].startswith("enc-")
    assert data["encounter_id"] != data["patient_name"]


def test_regression_existing_medications_salbutamol_and_cetirizine():
    # 1. Salbutamol and cetirizine are identified as existing medications
    data = get_analysis_result()
    meds = data["medications"]

    salbutamol = next((m for m in meds if "albuterol" in (m["normalized_name"] or "").lower() or "salbutamol" in m["mention"].lower()), None)
    assert salbutamol is not None, "Salbutamol must be extracted"
    assert salbutamol["status"] == MedicationStatus.CURRENTLY_TAKING.value
    assert salbutamol["rxcui"] == "435"

    cetirizine = next((m for m in meds if "cetirizine" in (m["normalized_name"] or "").lower() or "cetirizine" in m["mention"].lower()), None)
    assert cetirizine is not None, "Cetirizine must be extracted"
    assert cetirizine["status"] == MedicationStatus.CURRENTLY_TAKING.value
    assert cetirizine["rxcui"] == "20610"


def test_regression_paracetamol_historical_and_recommendation_split():
    # 2. Paracetamol has a historical-use mention and a separate recommendation mention
    data = get_analysis_result()
    meds = data["medications"]

    paracetamol_entries = [
        m for m in meds
        if (m.get("normalized_name") == "acetaminophen" or "paracetamol" in m["mention"].lower())
    ]
    assert len(paracetamol_entries) >= 2, f"Expected distinct paracetamol mentions, got: {paracetamol_entries}"

    statuses = [m["status"] for m in paracetamol_entries]
    assert MedicationStatus.PREVIOUSLY_TAKEN.value in statuses, "Must have previously_taken status for past paracetamol use"
    assert MedicationStatus.RECOMMENDED.value in statuses, "Must have recommended status for paracetamol recommendation"


def test_regression_amoxicillin_and_azithromycin_not_prescribed_or_currently_taking():
    # 3. Amoxicillin and azithromycin are not marked as prescribed or currently taken
    data = get_analysis_result()
    meds = data["medications"]

    amox = [m for m in meds if "amoxicillin" in (m["normalized_name"] or "").lower() or "amoxicillin" in m["mention"].lower()]
    for m in amox:
        assert m["status"] not in (MedicationStatus.PRESCRIBED.value, MedicationStatus.CURRENTLY_TAKING.value)

    azith = [m for m in meds if "azithromycin" in (m["normalized_name"] or "").lower() or "azithromycin" in m["mention"].lower()]
    for m in azith:
        assert m["status"] not in (MedicationStatus.PRESCRIBED.value, MedicationStatus.CURRENTLY_TAKING.value)
        assert m["status"] in (MedicationStatus.CONSIDERED_NOT_PRESCRIBED.value, MedicationStatus.NOT_RECOMMENDED.value)


def test_regression_budesonide_not_prescribed():
    # 4. Budesonide is not marked as prescribed
    data = get_analysis_result()
    meds = data["medications"]

    budesonide = [m for m in meds if "budesonide" in (m["normalized_name"] or "").lower() or "budesonide" in m["mention"].lower()]
    for m in budesonide:
        assert m["status"] != MedicationStatus.PRESCRIBED.value
        assert m["status"] in (MedicationStatus.CONSIDERED_NOT_PRESCRIBED.value, MedicationStatus.NOT_RECOMMENDED.value)


def test_regression_amoxicillin_allergy_rash():
    # 5. The amoxicillin-related rash is captured as an allergy/adverse-reaction history
    data = get_analysis_result()
    allergies = data["allergies"]
    assert len(allergies) > 0, "Allergies must be extracted"

    amox_or_pen = [
        a for a in allergies
        if "amoxicillin" in a["substance"].lower() or "penicillin" in a["substance"].lower()
    ]
    assert len(amox_or_pen) > 0
    assert any("rash" in a["reaction"].lower() for a in amox_or_pen)
    assert any(a["timing"] == "historical" for a in amox_or_pen)


def test_regression_no_medication_automatically_marked_active():
    # 6. No medication is automatically marked active simply because it was mentioned
    data = get_analysis_result()
    meds = data["medications"]
    for m in meds:
        name = (m["normalized_name"] or m["mention"]).lower()
        if name in ("amoxicillin", "azithromycin", "budesonide"):
            assert m["status"] not in (MedicationStatus.CURRENTLY_TAKING.value, MedicationStatus.PRESCRIBED.value)


def test_regression_chest_pain_and_confusion_not_positive_symptoms():
    # 7. Chest pain and confusion do not appear as positive symptoms
    data = get_analysis_result()
    entities = data["entities"]

    # In entities list, chest pain and confusion must NEVER be marked 'positive'
    for e in entities:
        if e["text"].lower() in ("chest pain", "confusion"):
            assert e.get("assertion") in ("denied", "uncertain"), f"Expected non-positive assertion for {e['text']}, got {e.get('assertion')}"
            assert e.get("assertion") != "positive", f"Chest pain and confusion must not appear as positive symptoms"

    # In SOAP subjective and assessment, chest pain and confusion must not appear as positive complaints
    soap = data["soap_note"]
    subj_str = " ".join(soap.get("subjective", [])).lower()
    assess_str = " ".join(soap.get("assessment", [])).lower()

    # If mentioned, must be explicitly under denied / pertinent negatives
    assert "chief complaints" in subj_str
    cc_line = next((line.lower() for line in soap.get("subjective", []) if "chief complaints" in line.lower()), "")
    assert "chest pain" not in cc_line
    assert "confusion" not in cc_line
    assert "chest pain" not in assess_str
    assert "confusion" not in assess_str


def test_regression_conditional_chest_xray_not_confirmed_order():
    # 8. A conditional X-ray discussion does not become a confirmed order
    data = get_analysis_result()
    invs = data["investigations"]
    xray = next((i for i in invs if "x-ray" in i["mention"].lower() or "xray" in i["mention"].lower()), None)
    assert xray is not None, "Chest X-ray must be extracted in investigations"
    assert xray["status"] != InvestigationStatus.ORDERED.value, "Chest X-ray must not be marked as ORDERED"
    assert xray["status"] in (InvestigationStatus.CONDITIONAL.value, InvestigationStatus.CONSIDERED.value)

    # In FHIR bundle, any ServiceRequest for chest x-ray must NOT have intent="order" with status="active"
    bundle = data["fhir_bundle"]
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == "ServiceRequest":
            code_text = (res.get("code", {}).get("text") or "").lower()
            if "x-ray" in code_text or "xray" in code_text:
                assert res.get("intent") != "order" or res.get("status") != "active"


def test_regression_no_unsupported_diagnosis_or_dosage_fabricated():
    # 9. No unsupported diagnosis, dosage, or test result is generated
    data = get_analysis_result()
    soap = data["soap_note"]
    # Verify no fabricated vital signs (like BP 120/80)
    obj_str = " ".join(soap.get("objective", []))
    assert "120/80" not in obj_str
    assert "98.6" not in obj_str


def test_regression_dossier_entities_and_fhir_consistency():
    # 10. The dossier, entities table, and FHIR JSON remain consistent
    data = get_analysis_result()
    bundle = data["fhir_bundle"]
    meds = data["medications"]

    # Verify FHIR Patient resource has Rahul Verma
    patient_resources = [e["resource"] for e in bundle.get("entry", []) if e.get("resource", {}).get("resourceType") == "Patient"]
    assert len(patient_resources) > 0
    p_names = patient_resources[0].get("name", [])
    assert any("Rahul" in n.get("text", "") for n in p_names)

    # Verify FHIR Practitioner resource has Dr. Meera Sharma
    pract_resources = [e["resource"] for e in bundle.get("entry", []) if e.get("resource", {}).get("resourceType") == "Practitioner"]
    assert len(pract_resources) > 0
    doc_names = pract_resources[0].get("name", [])
    assert any("Meera" in n.get("text", "") for n in doc_names)

    # Verify AllergyIntolerance in FHIR
    allergy_resources = [e["resource"] for e in bundle.get("entry", []) if e.get("resource", {}).get("resourceType") == "AllergyIntolerance"]
    assert len(allergy_resources) > 0

    # Verify no active MedicationRequest/Statement for amoxicillin or azithromycin
    med_resources = [
        e["resource"] for e in bundle.get("entry", [])
        if e.get("resource", {}).get("resourceType") in ("MedicationRequest", "MedicationStatement")
    ]
    for mr in med_resources:
        text = (mr.get("medicationCodeableConcept", {}).get("text") or "").lower()
        if "amoxicillin" in text or "azithromycin" in text:
            # If present, status must not be active order
            assert mr.get("status") != "active"


def test_regression_no_misleading_duplicates_and_auditability():
    # 11. Repeated drug mentions do not produce misleading duplicate medication entries
    # 12. Every generated clinical assertion can be traced to the input transcript
    data = get_analysis_result()
    meds = data["medications"]

    # Check that salbutamol appears only once
    salbutamol_count = sum(1 for m in meds if "albuterol" in (m["normalized_name"] or "").lower() or "salbutamol" in m["mention"].lower())
    assert salbutamol_count == 1, f"Salbutamol should only have 1 consolidated entry, got {salbutamol_count}"

    # Check that cetirizine appears only once
    cetirizine_count = sum(1 for m in meds if "cetirizine" in (m["normalized_name"] or "").lower() or "cetirizine" in m["mention"].lower())
    assert cetirizine_count == 1, f"Cetirizine should only have 1 consolidated entry, got {cetirizine_count}"

    # Traceability: each med has context
    for m in meds:
        assert m["context"] is not None and len(m["context"]) > 0


def test_regression_report_html_generation():
    data = get_analysis_result()
    res = client.post("/v1/report", json=data)
    assert res.status_code == 200
    html = res.text
    assert "Rahul Verma" in html
    assert "Dr. Meera Sharma" in html
    assert "Salbutamol" in html or "salbutamol" in html
    assert "Allergies" in html or "Allergy" in html
