from __future__ import annotations

from typing import Any
from .schemas import ClinicalEntity, EntityType, Medication


def _ref(entity: ClinicalEntity) -> dict[str, Any]:
    return {"extension": [{"url": "https://mediscribe.local/fhir/StructureDefinition/transcript-provenance", "valueString": f"turn={entity.provenance.turn_id}; chars={entity.provenance.start_char}-{entity.provenance.end_char}"}]}


def build_bundle(encounter_id: str, patient_id: str | None, entities: list[ClinicalEntity], medications: list[Medication]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    subject = {"reference": f"Patient/{patient_id}"} if patient_id else None
    for entity in entities:
        if entity.type in (EntityType.SYMPTOM, EntityType.ADVERSE_EVENT):
            resource: dict[str, Any] = {"resourceType": "Condition", "clinicalStatus": {"text": "unverified"}, "code": {"text": entity.text}, **_ref(entity)}
        elif entity.type == EntityType.TEST:
            resource = {"resourceType": "ServiceRequest", "status": "draft", "intent": "proposal", "code": {"text": entity.text}, **_ref(entity)}
        else: continue
        if subject: resource["subject"] = subject
        entries.append({"resource": resource})
    for med in medications:
        resource = {"resourceType": "MedicationStatement", "status": "unknown", "medicationCodeableConcept": {"text": med.normalized_name or med.mention}, "note": [{"text": "Unverified transcript extraction; clinician review required."}]}
        if med.rxcui: resource["medicationCodeableConcept"]["coding"] = [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": med.rxcui, "display": med.normalized_name}]
        if subject: resource["subject"] = subject
        entries.append({"resource": resource})
    return {"resourceType": "Bundle", "type": "collection", "identifier": {"value": encounter_id}, "entry": entries}
