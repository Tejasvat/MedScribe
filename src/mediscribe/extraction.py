from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from uuid import uuid4

from .schemas import ClinicalEntity, EntityType, Provenance, TranscriptTurn


class Extractor(ABC):
    @abstractmethod
    def extract(self, turns: Iterable[TranscriptTurn]) -> list[ClinicalEntity]: ...


class RuleBasedExtractor(Extractor):
    """Transparent baseline and safe fallback when no fine-tuned model is present.

    Extended lexicon covers a wide range of clinical terminology encountered
    in general-practice consultations, discharge summaries, and patient notes.
    """

    TERMS: dict[EntityType, tuple[str, ...]] = {
        EntityType.SYMPTOM: (
            # General
            "fever", "cough", "pain", "headache", "vomiting", "diarrhea",
            "fatigue", "breathlessness", "nausea", "dizziness", "drowsiness",
            # Respiratory
            "wheezing", "shortness of breath", "chest pain", "sore throat",
            "runny nose", "nasal congestion", "sneezing", "hemoptysis",
            # Gastrointestinal
            "abdominal pain", "constipation", "bloating", "heartburn",
            "loss of appetite", "blood in stool", "dysphagia",
            # Musculoskeletal
            "joint pain", "back pain", "muscle pain", "stiffness", "swelling",
            "weakness", "numbness", "tingling",
            # Neurological
            "seizure", "confusion", "memory loss", "tremor", "blurred vision",
            "vertigo", "syncope", "insomnia",
            # Cardiovascular
            "palpitations", "chest tightness", "edema", "leg swelling",
            # Dermatological
            "rash", "itching", "hives", "skin lesion", "bruising",
            # General / Constitutional
            "weight loss", "weight gain", "night sweats", "chills",
            "malaise", "lethargy", "dehydration",
        ),
        EntityType.ADVERSE_EVENT: (
            "allergy", "allergic reaction", "anaphylaxis",
            "drug reaction", "side effect", "adverse reaction",
            "stevens-johnson", "hepatotoxicity", "nephrotoxicity",
            "gi bleeding", "gastrointestinal bleeding",
            "hypotension", "hypertension", "tachycardia", "bradycardia",
            "photosensitivity", "agranulocytosis", "thrombocytopenia",
        ),
        EntityType.TEST: (
            # Blood tests
            "complete blood count", "cbc", "blood test", "hemoglobin",
            "hematocrit", "platelet count", "white blood cell count", "wbc",
            "red blood cell count", "rbc", "blood glucose", "fasting glucose",
            "hba1c", "glycated hemoglobin",
            # Chemistry panel
            "basic metabolic panel", "bmp", "comprehensive metabolic panel", "cmp",
            "electrolytes", "sodium", "potassium", "creatinine", "bun",
            "blood urea nitrogen", "liver function test", "lft",
            "kidney function test", "gfr", "egfr",
            # Lipid panel
            "lipid panel", "cholesterol", "ldl", "hdl", "triglycerides",
            # Cardiac
            "troponin", "bnp", "ecg", "electrocardiogram", "ekg",
            "echocardiogram", "echo", "stress test", "cardiac catheterization",
            # Imaging
            "x-ray", "xray", "mri", "ct scan", "cat scan", "ultrasound",
            "mammogram", "pet scan", "bone scan", "dexa scan",
            # Urinalysis
            "urine test", "urinalysis", "urine culture",
            # Thyroid
            "tsh", "thyroid function test", "t3", "t4", "free t4",
            # Coagulation
            "inr", "pt", "ptt", "prothrombin time", "d-dimer",
            # Microbiology
            "blood culture", "sputum culture", "wound culture",
            "sensitivity test", "antibiogram",
            # Other
            "biopsy", "cytology", "pathology", "endoscopy", "colonoscopy",
            "spirometry", "pulmonary function test", "pft",
            "lumbar puncture", "spinal tap",
        ),
        EntityType.DRUG: (
            # Analgesics / Antipyretics
            "paracetamol", "acetaminophen", "ibuprofen", "aspirin",
            "naproxen", "diclofenac", "celecoxib", "tramadol",
            "morphine", "codeine", "oxycodone", "fentanyl",
            # Antibiotics
            "amoxicillin", "azithromycin", "ciprofloxacin", "levofloxacin",
            "doxycycline", "metronidazole", "clindamycin", "cephalexin",
            "ceftriaxone", "augmentin", "amoxicillin-clavulanate",
            "penicillin", "erythromycin", "trimethoprim", "nitrofurantoin",
            # Anticoagulants / Antiplatelets
            "warfarin", "clopidogrel", "heparin", "enoxaparin",
            "rivaroxaban", "apixaban", "dabigatran", "ticagrelor",
            # Cardiovascular
            "metoprolol", "atenolol", "propranolol", "amlodipine",
            "lisinopril", "enalapril", "ramipril", "losartan", "valsartan",
            "hydrochlorothiazide", "furosemide", "spironolactone",
            "atorvastatin", "rosuvastatin", "simvastatin",
            "nitroglycerin", "digoxin", "amiodarone",
            # Diabetes
            "metformin", "insulin", "glipizide", "glyburide",
            "sitagliptin", "empagliflozin", "semaglutide", "liraglutide",
            # Respiratory
            "salbutamol", "albuterol", "ipratropium", "fluticasone",
            "montelukast", "budesonide", "tiotropium", "theophylline",
            # GI
            "omeprazole", "pantoprazole", "lansoprazole", "ranitidine",
            "ondansetron", "metoclopramide", "loperamide", "bismuth",
            # Psychiatric / Neurological
            "sertraline", "fluoxetine", "escitalopram", "venlafaxine",
            "duloxetine", "amitriptyline", "gabapentin", "pregabalin",
            "carbamazepine", "valproate", "levetiracetam", "phenytoin",
            "diazepam", "lorazepam", "alprazolam", "zolpidem",
            "quetiapine", "risperidone", "olanzapine", "lithium",
            # Steroids
            "prednisone", "prednisolone", "dexamethasone", "hydrocortisone",
            "methylprednisolone",
            # Thyroid
            "levothyroxine", "methimazole",
            # Allergy
            "cetirizine", "loratadine", "diphenhydramine", "fexofenadine",
            "montelukast",
            # Others
            "allopurinol", "colchicine", "methotrexate",
        ),
    }

    PATTERNS: dict[EntityType, re.Pattern[str]] = {
        # Dosage: catches "500 mg", "2.5 mL", "100 mcg", "10,000 units", "1 g"
        EntityType.DOSAGE: re.compile(
            r"\b\d{1,5}(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|mL|units?|IU|mmol|mEq)\b",
            re.I,
        ),
        # Frequency: "twice a day", "every 8 hours", "three times daily", "q6h", "BID", "TID", "QID"
        EntityType.FREQUENCY: re.compile(
            r"\b(?:"
            r"(?:once|twice|thrice)\s+(?:a|per)\s+(?:day|daily|week|weekly)|"
            r"(?:every|q)\s*\d+\s*(?:h(?:ours?)?|min(?:utes?)?)|"
            r"(?:one|two|three|four)\s+times?\s+(?:a\s+)?(?:day|daily|week|weekly)|"
            r"(?:once|twice)\s+daily|"
            r"(?:b\.?i\.?d\.?|t\.?i\.?d\.?|q\.?i\.?d\.?|q\.?d\.?|p\.?r\.?n\.?|"
            r"q\.?h\.?s\.?|a\.?c\.?|p\.?c\.?|stat|as needed|at bedtime|"
            r"in the morning|at night|before meals?|after meals?|with food)"
            r")\b",
            re.I,
        ),
        # Duration: "for 5 days", "since 2 weeks", "for 3 months", "past 2 years"
        EntityType.DURATION: re.compile(
            r"\b(?:for|since|past|last|over the past|over the last|x)\s*"
            r"\d+\s*(?:day|days|week|weeks|month|months|year|years)\b",
            re.I,
        ),
    }

    def extract(self, turns: Iterable[TranscriptTurn]) -> list[ClinicalEntity]:
        output: list[ClinicalEntity] = []
        for turn in turns:
            # Term-based extraction (lexicon lookup)
            for entity_type, terms in self.TERMS.items():
                pattern = re.compile(
                    r"\b(?:" + "|".join(map(re.escape, terms)) + r")\b", re.I
                )
                output.extend(
                    self._from_matches(turn, entity_type, pattern.finditer(turn.text), 0.82)
                )
            # Pattern-based extraction (regex)
            for entity_type, pattern in self.PATTERNS.items():
                output.extend(
                    self._from_matches(turn, entity_type, pattern.finditer(turn.text), 0.76)
                )
        return self._deduplicate(output)

    @staticmethod
    def _from_matches(
        turn: TranscriptTurn,
        entity_type: EntityType,
        matches: Iterable[re.Match[str]],
        score: float,
    ) -> list[ClinicalEntity]:
        return [
            ClinicalEntity(
                entity_id=str(uuid4()),
                type=entity_type,
                text=m.group(),
                confidence=score,
                provenance=Provenance(
                    turn_id=turn.turn_id,
                    start_char=m.start(),
                    end_char=m.end(),
                    source_text=turn.text,
                ),
            )
            for m in matches
        ]

    @staticmethod
    def _deduplicate(entities: list[ClinicalEntity]) -> list[ClinicalEntity]:
        seen: set[tuple[str, str, str]] = set()
        return [
            e
            for e in entities
            if not (
                (key := (e.provenance.turn_id, e.type.value, e.text.lower())) in seen
                or seen.add(key)  # type: ignore[func-returns-value]
            )
        ]


class TransformersExtractor(Extractor):
    """Adapter for a locally hosted fine-tuned token-classification model."""

    def __init__(self, model_id: str):
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "Install the 'ml' extra to use MEDISCRIBE_NER_MODEL"
            ) from exc
        self.pipeline = pipeline(
            "token-classification",
            model=model_id,
            tokenizer=model_id,
            aggregation_strategy="simple",
        )

    def extract(self, turns: Iterable[TranscriptTurn]) -> list[ClinicalEntity]:
        output: list[ClinicalEntity] = []
        for turn in turns:
            for item in self.pipeline(turn.text):
                label = item["entity_group"].lower().replace("-", "_")
                if label not in EntityType._value2member_map_:
                    continue
                output.append(
                    ClinicalEntity(
                        entity_id=str(uuid4()),
                        type=EntityType(label),
                        text=item["word"],
                        confidence=float(item["score"]),
                        provenance=Provenance(
                            turn_id=turn.turn_id,
                            start_char=int(item["start"]),
                            end_char=int(item["end"]),
                            source_text=turn.text,
                        ),
                    )
                )
        return output


def get_extractor() -> Extractor:
    model_id = os.getenv("MEDISCRIBE_NER_MODEL")
    return TransformersExtractor(model_id) if model_id else RuleBasedExtractor()
