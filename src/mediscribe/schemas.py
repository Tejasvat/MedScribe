from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class Speaker(str, Enum):
    PATIENT = "patient"
    CLINICIAN = "clinician"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    SYMPTOM = "symptom"
    DRUG = "drug"
    DOSAGE = "dosage"
    FREQUENCY = "frequency"
    DURATION = "duration"
    TEST = "test"
    ADVERSE_EVENT = "adverse_event"


class TranscriptTurn(BaseModel):
    turn_id: str = Field(min_length=1, max_length=128)
    speaker: Speaker = Speaker.UNKNOWN
    text: str = Field(min_length=1, max_length=10_000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)

    @field_validator("end_ms")
    @classmethod
    def end_after_start(cls, end: int | None, info: Any) -> int | None:
        start = info.data.get("start_ms")
        if end is not None and start is not None and end < start:
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return end


class AnalyzeRequest(BaseModel):
    encounter_id: str = Field(min_length=1, max_length=128)
    patient_id: str | None = Field(default=None, max_length=128)
    turns: list[TranscriptTurn] = Field(min_length=1, max_length=500)


class Provenance(BaseModel):
    turn_id: str
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    source_text: str


class ClinicalEntity(BaseModel):
    entity_id: str
    type: EntityType
    text: str
    normalized_text: str | None = None
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance


class Medication(BaseModel):
    entity_id: str
    mention: str
    rxcui: str | None = None
    normalized_name: str | None = None
    normalization_confidence: float = Field(ge=0, le=1)


class SafetyAlert(BaseModel):
    alert_id: str
    severity: str
    category: str
    message: str
    medication_entity_ids: list[str]
    requires_clinician_review: bool = True


class SoapNote(BaseModel):
    subjective: list[str]
    objective: list[str]
    assessment: list[str]
    plan: list[str]
    disclaimer: str


class AnalyzeResponse(BaseModel):
    encounter_id: str
    turns: list[TranscriptTurn] = Field(default_factory=list)
    entities: list[ClinicalEntity]
    medications: list[Medication]
    safety_alerts: list[SafetyAlert]
    soap_note: SoapNote
    fhir_bundle: dict[str, Any]
    requires_clinician_review: bool = True
