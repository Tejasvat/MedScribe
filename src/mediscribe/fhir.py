from __future__ import annotations

from typing import Any
from .schemas import (
    AllergyRecord,
    ClinicalEntity,
    EntityType,
    Investigation,
    InvestigationStatus,
    Medication,
    MedicationStatus,
)


def _ref(entity: ClinicalEntity) -> dict[str, Any]:
    return {
        "extension": [
            {
                "url": "https://mediscribe.local/fhir/StructureDefinition/transcript-provenance",
                "valueString": f"turn={entity.provenance.turn_id}; chars={entity.provenance.start_char}-{entity.provenance.end_char}",
            }
        ]
    }


def build_bundle(
    encounter_id: str,
    patient_id: str | None,
    entities: list[ClinicalEntity],
    medications: list[Medication],
    allergies: list[AllergyRecord] | None = None,
    investigations: list[Investigation] | None = None,
    patient_name: str | None = None,
    physician_name: str | None = None,
) -> dict[str, Any]:
    """Build a compliant, verified FHIR R4 Bundle maintaining clinical consistency."""
    entries: list[dict[str, Any]] = []

    # 1. Patient Resource
    pat_res_id = patient_id or (
        patient_name.lower().replace(" ", "-") if patient_name else f"pat-{encounter_id}"
    )
    pat_resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": pat_res_id,
    }
    if patient_name:
        parts = patient_name.split()
        pat_resource["name"] = [
            {
                "use": "official",
                "text": patient_name,
                "family": parts[-1] if len(parts) > 1 else patient_name,
                "given": parts[:-1] if len(parts) > 1 else [patient_name],
            }
        ]
    subject = {"reference": f"Patient/{pat_res_id}"}
    entries.append({"resource": pat_resource})

    # 2. Practitioner Resource
    doc_res_id = "practitioner-1"
    practitioner_resource: dict[str, Any] = {
        "resourceType": "Practitioner",
        "id": doc_res_id,
    }
    if physician_name:
        clean_name = physician_name.replace("Dr.", "").replace("Doctor", "").strip()
        parts = clean_name.split()
        practitioner_resource["name"] = [
            {
                "use": "official",
                "text": physician_name,
                "prefix": ["Dr."],
                "family": parts[-1] if len(parts) > 1 else clean_name,
                "given": parts[:-1] if len(parts) > 1 else [clean_name],
            }
        ]
    entries.append({"resource": practitioner_resource})

    # 3. Encounter Resource
    entries.append(
        {
            "resource": {
                "resourceType": "Encounter",
                "id": encounter_id,
                "status": "finished",
                "class": {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "AMB",
                    "display": "ambulatory",
                },
                "subject": subject,
                "participant": [{"individual": {"reference": f"Practitioner/{doc_res_id}"}}],
            }
        }
    )

    # 4. AllergyIntolerance Resources
    if allergies:
        for allergy in allergies:
            allergy_res: dict[str, Any] = {
                "resourceType": "AllergyIntolerance",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active",
                            "display": "Active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                            "code": "confirmed",
                            "display": "Confirmed",
                        }
                    ]
                },
                "type": "allergy",
                "category": ["medication"],
                "code": {"text": allergy.substance.title()},
                "patient": subject,
                "note": [{"text": allergy.supporting_sentence}],
            }
            if allergy.reaction:
                allergy_res["reaction"] = [
                    {
                        "manifestation": [{"text": allergy.reaction.title()}],
                        "description": f"Historical reaction: {allergy.reaction}",
                    }
                ]
            entries.append({"resource": allergy_res})

    # 5. Condition Resources (Positive Symptoms & Pre-existing Diagnoses)
    for entity in entities:
        if entity.type in (EntityType.SYMPTOM, EntityType.DIAGNOSIS):
            # Only create active Conditions for positive findings
            if entity.assertion == "denied":
                continue  # Never create positive condition for denied symptom

            is_confirmed = entity.assertion == "positive"
            resource: dict[str, Any] = {
                "resourceType": "Condition",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                            "display": "Active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": "confirmed" if is_confirmed else "provisional",
                            "display": "Confirmed" if is_confirmed else "Provisional",
                        }
                    ]
                },
                "code": {"text": entity.text},
                "subject": subject,
                **_ref(entity),
            }
            entries.append({"resource": resource})

    # 6. ServiceRequest Resources (Investigations)
    if investigations:
        for inv in investigations:
            if inv.status == InvestigationStatus.ORDERED:
                stat_val = "active"
                intent_val = "order"
            elif inv.status == InvestigationStatus.RECOMMENDED:
                stat_val = "draft"
                intent_val = "proposal"
            else:
                stat_val = "draft"
                intent_val = "proposal"

            s_req: dict[str, Any] = {
                "resourceType": "ServiceRequest",
                "status": stat_val,
                "intent": intent_val,
                "code": {"text": inv.mention},
                "subject": subject,
            }
            if inv.status == InvestigationStatus.CONDITIONAL:
                s_req["note"] = [
                    {"text": f"Conditional investigation: {inv.condition_detail or 'if symptoms worsen'}; not currently ordered."}
                ]
            elif inv.status == InvestigationStatus.DISCUSSED:
                s_req["note"] = [
                    {"text": "Discussed during encounter; no formal diagnostic order placed."}
                ]
            entries.append({"resource": s_req})
    else:
        # Fallback to test entities
        for entity in entities:
            if entity.type == EntityType.TEST:
                entries.append(
                    {
                        "resource": {
                            "resourceType": "ServiceRequest",
                            "status": "draft",
                            "intent": "proposal",
                            "code": {"text": entity.text},
                            "subject": subject,
                            **_ref(entity),
                        }
                    }
                )

    # 7. MedicationStatement & MedicationRequest Resources
    for med in medications:
        # Do not create active MedicationStatements for allergy-related mentions!
        if med.status == MedicationStatus.ALLERGY_RELATED:
            continue

        concept: dict[str, Any] = {"text": med.normalized_name or med.mention}
        if med.rxcui:
            concept["coding"] = [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": med.rxcui,
                    "display": med.normalized_name,
                }
            ]

        if med.status == MedicationStatus.PRESCRIBED:
            # Prescribed -> MedicationRequest
            med_req: dict[str, Any] = {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": concept,
                "subject": subject,
            }
            if med.dosage or med.frequency:
                med_req["dosageInstruction"] = [
                    {
                        "text": f"{med.dosage or ''} {med.frequency or ''}".strip(),
                    }
                ]
            entries.append({"resource": med_req})

        elif med.status == MedicationStatus.CURRENTLY_TAKING:
            # Currently taking -> MedicationStatement active
            med_stmt: dict[str, Any] = {
                "resourceType": "MedicationStatement",
                "status": "active",
                "medicationCodeableConcept": concept,
                "subject": subject,
                "note": [{"text": f"Baseline active therapy: {med.context or med.mention}"}],
            }
            entries.append({"resource": med_stmt})

        elif med.status == MedicationStatus.PREVIOUSLY_TAKEN:
            # Previously taken -> MedicationStatement stopped
            med_stmt = {
                "resourceType": "MedicationStatement",
                "status": "stopped",
                "medicationCodeableConcept": concept,
                "subject": subject,
                "note": [{"text": f"Historical medication: {med.context or med.mention}"}],
            }
            entries.append({"resource": med_stmt})

        elif med.status == MedicationStatus.RECOMMENDED:
            # Recommended -> MedicationStatement intended
            med_stmt = {
                "resourceType": "MedicationStatement",
                "status": "intended",
                "medicationCodeableConcept": concept,
                "subject": subject,
                "note": [{"text": f"Recommended OTC relief: {med.dosage or ''} {med.frequency or ''}".strip()}],
            }
            entries.append({"resource": med_stmt})

        elif med.status in (MedicationStatus.CONSIDERED_NOT_PRESCRIBED, MedicationStatus.NOT_RECOMMENDED):
            # Not prescribed / not recommended -> status: not-taken
            med_stmt = {
                "resourceType": "MedicationStatement",
                "status": "not-taken",
                "medicationCodeableConcept": concept,
                "subject": subject,
                "note": [{"text": f"Discussed but not prescribed: {med.context or med.mention}"}],
            }
            entries.append({"resource": med_stmt})

        else:
            # Unknown status fallback
            med_stmt = {
                "resourceType": "MedicationStatement",
                "status": "unknown",
                "medicationCodeableConcept": concept,
                "subject": subject,
                "note": [{"text": "Transcript mention under clinician verification"}],
            }
            entries.append({"resource": med_stmt})

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "identifier": {"value": encounter_id},
        "entry": entries,
    }
