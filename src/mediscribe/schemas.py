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
    ROUTE = "route"
    TEST = "test"
    ADVERSE_EVENT = "adverse_event"
    DIAGNOSIS = "diagnosis"
    MEDICAL_HISTORY = "medical_history"
    ALLERGY = "allergy"
    PATIENT = "patient"
    PHYSICIAN = "physician"


class MedicationStatus(str, Enum):
    CURRENTLY_TAKING = "currently_taking"
    PREVIOUSLY_TAKEN = "previously_taken"
    PRESCRIBED = "prescribed"
    RECOMMENDED = "recommended"
    CONSIDERED_NOT_PRESCRIBED = "considered_not_prescribed"
    NOT_RECOMMENDED = "not_recommended"
    ALLERGY_RELATED = "allergy_related"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        names = {
            MedicationStatus.CURRENTLY_TAKING: "Currently taking",
            MedicationStatus.PREVIOUSLY_TAKEN: "Previously taken",
            MedicationStatus.PRESCRIBED: "Prescribed",
            MedicationStatus.RECOMMENDED: "Recommended",
            MedicationStatus.CONSIDERED_NOT_PRESCRIBED: "Considered (not prescribed)",
            MedicationStatus.NOT_RECOMMENDED: "Not recommended",
            MedicationStatus.ALLERGY_RELATED: "Allergy-related",
            MedicationStatus.UNKNOWN: "Unknown",
        }
        return names.get(self, "Unknown")


class InvestigationStatus(str, Enum):
    ORDERED = "ordered"
    RECOMMENDED = "recommended"
    CONSIDERED = "considered"
    CONDITIONAL = "conditional"
    COMPLETED = "completed"
    DISCUSSED = "discussed"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        names = {
            InvestigationStatus.ORDERED: "Ordered",
            InvestigationStatus.RECOMMENDED: "Recommended",
            InvestigationStatus.CONSIDERED: "Considered",
            InvestigationStatus.CONDITIONAL: "Conditional",
            InvestigationStatus.COMPLETED: "Completed",
            InvestigationStatus.DISCUSSED: "Discussed",
            InvestigationStatus.UNKNOWN: "Unknown",
        }
        return names.get(self, "Discussed")


class SymptomAssertion(str, Enum):
    POSITIVE = "positive"
    DENIED = "denied"
    HISTORICAL = "historical"
    UNCERTAIN = "uncertain"


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
    patient_name: str | None = Field(default=None, max_length=128)
    physician_name: str | None = Field(default=None, max_length=128)
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
    assertion: str = "positive"  # "positive", "denied", "historical", "uncertain", "conditional"
    status: str | None = None


class Medication(BaseModel):
    entity_id: str
    mention: str
    rxcui: str | None = None
    normalized_name: str | None = None
    normalization_confidence: float = Field(default=0.9, ge=0, le=1)
    status: MedicationStatus = MedicationStatus.UNKNOWN
    status_display: str = "Unknown"
    dosage: str | None = None
    frequency: str | None = None
    route: str | None = None
    duration: str | None = None
    context: str | None = None
    turn_id: str | None = None


class AllergyRecord(BaseModel):
    allergy_id: str
    substance: str
    reaction: str | None = None
    timing: str = "historical"  # "historical" | "current" | "unknown"
    source: str = "patient"
    supporting_sentence: str
    turn_id: str | None = None


class Investigation(BaseModel):
    investigation_id: str
    mention: str
    normalized_name: str | None = None
    status: InvestigationStatus = InvestigationStatus.DISCUSSED
    status_display: str = "Discussed"
    condition_detail: str | None = None
    result: str | None = None
    turn_id: str | None = None
    supporting_sentence: str | None = None


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
    pertinent_negatives: list[str] = Field(default_factory=list)
    medical_history: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    encounter_id: str
    patient_id: str | None = None
    patient_name: str | None = None
    patient_age: int | str | None = None
    physician_id: str | None = None
    physician_name: str | None = None
    turns: list[TranscriptTurn] = Field(default_factory=list)
    entities: list[ClinicalEntity]
    medications: list[Medication]
    investigations: list[Investigation] = Field(default_factory=list)
    allergies: list[AllergyRecord] = Field(default_factory=list)
    safety_alerts: list[SafetyAlert]
    soap_note: SoapNote
    fhir_bundle: dict[str, Any]
    requires_clinician_review: bool = True


class AudioTranscriptSegment(BaseModel):
    segment_id: str
    speaker_id: str  # e.g., "SPEAKER_00"
    role: str = "unknown"  # "doctor", "patient", "other", "unknown"
    start_sec: float = 0.0
    end_sec: float = 0.0
    text: str = Field(min_length=1)


class AudioStatusResponse(BaseModel):
    job_id: str
    filename: str
    status: str  # "queued", "validating", "transcribing", "diarizing", "completed", "failed"
    progress: int = Field(ge=0, le=100)
    segments: list[AudioTranscriptSegment] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    speaker_role_map: dict[str, str] = Field(default_factory=dict)
    error_message: str | None = None
    diarization_warning: str | None = None
    duration_sec: float = 0.0


class AudioAnalyzeRequest(BaseModel):
    encounter_id: str = Field(min_length=1, max_length=128)
    patient_id: str | None = Field(default=None, max_length=128)
    patient_name: str | None = Field(default=None, max_length=128)
    physician_name: str | None = Field(default=None, max_length=128)
    segments: list[AudioTranscriptSegment] = Field(min_length=1)
    speaker_roles: dict[str, str] = Field(default_factory=dict)  # {"SPEAKER_00": "doctor", "SPEAKER_01": "patient"}

