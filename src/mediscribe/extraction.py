from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from uuid import uuid4

from .schemas import ClinicalEntity, EntityType, Provenance, TranscriptTurn


def extract_identities(
    turns: Iterable[TranscriptTurn],
) -> tuple[str | None, int | str | None, str | None]:
    """Extract patient name, age, and physician name from dialogue turns."""
    patient_name: str | None = None
    patient_age: int | str | None = None
    physician_name: str | None = None

    for turn in turns:
        text = turn.text

        # 1. Physician Extraction
        if not physician_name:
            # "Dr. Meera Sharma", "Doctor Meera Sharma", "I am Dr. Meera Sharma"
            doc_match = re.search(
                r"\b(?:I am|this is|attending:?|physician:?)?\s*(?:Dr\.?|Doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
                text,
            )
            if doc_match:
                physician_name = f"Dr. {doc_match.group(1).strip()}"
            else:
                doc_title = re.search(r"\bDr\.?\s+([A-Z][a-z]+)\b", text)
                if doc_title:
                    physician_name = f"Dr. {doc_title.group(1).strip()}"

        # 2. Patient Extraction
        if not patient_name:
            # "You must be Rahul Verma", "Patient: Rahul Verma", "Good morning Mr. Rahul Verma"
            pat_match = re.search(
                r"(?:You must be|patient:\s*|patient name:\s*|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
                text,
                re.IGNORECASE,
            )
            if pat_match:
                patient_name = pat_match.group(1).strip()

        # 3. Patient Age
        if not patient_age:
            age_match = re.search(r"\bage\s+(\d{1,3})\b", text, re.IGNORECASE) or re.search(
                r"\b(\d{1,3})\s*(?:years?\s*old|yo|y/o)\b", text, re.IGNORECASE
            )
            if age_match:
                try:
                    patient_age = int(age_match.group(1))
                except ValueError:
                    patient_age = age_match.group(1)

    return patient_name, patient_age, physician_name


class Extractor(ABC):
    @abstractmethod
    def extract(self, turns: Iterable[TranscriptTurn]) -> list[ClinicalEntity]: ...


class RuleBasedExtractor(Extractor):
    """Transparent baseline and clinical NER rule extractor with context awareness."""

    TERMS: dict[EntityType, tuple[str, ...]] = {
        EntityType.SYMPTOM: (
            # General & Constitutional
            "fever", "cough", "pain", "headache", "vomiting", "diarrhea",
            "fatigue", "breathlessness", "mild breathlessness", "nausea", "dizziness", "drowsiness",
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
            "rash", "skin rash", "itching", "hives", "skin lesion", "bruising",
            # Constitutional
            "weight loss", "weight gain", "night sweats", "chills",
            "malaise", "lethargy", "dehydration",
        ),
        EntityType.ADVERSE_EVENT: (
            "allergy", "allergic reaction", "anaphylaxis",
            "drug reaction", "side effect", "adverse reaction",
            "rash", "skin rash", "hives",
            "stevens-johnson", "hepatotoxicity", "nephrotoxicity",
            "gi bleeding", "gastrointestinal bleeding",
            "hypotension", "hypertension", "tachycardia", "bradycardia",
            "photosensitivity", "agranulocytosis", "thrombocytopenia",
        ),
        EntityType.DIAGNOSIS: (
            "mild asthma", "asthma", "hypertension", "type 2 diabetes", "diabetes",
            "atrial fibrillation", "pneumonia", "bacterial pneumonia",
            "acute pharyngitis", "pharyngitis", "bronchitis", "copd",
            "heart failure", "hyperlipidemia", "covid-19",
        ),
        EntityType.TEST: (
            # COVID & Microbiology
            "covid-19 antigen test", "covid antigen test", "covid-19 test", "covid test",
            "antigen test", "rapid strep test", "throat culture",
            "blood culture", "sputum culture", "wound culture",
            "sensitivity test", "antibiogram",
            # Blood tests & CBC
            "complete blood count", "cbc", "blood test", "hemoglobin",
            "hematocrit", "platelet count", "white blood cell count", "wbc",
            "red blood cell count", "rbc", "blood glucose", "fasting glucose",
            "hba1c", "glycated hemoglobin",
            # Chemistry panel & renal/liver
            "basic metabolic panel", "bmp", "comprehensive metabolic panel", "cmp",
            "electrolytes", "sodium", "potassium", "serum creatinine", "creatinine", "bun",
            "blood urea nitrogen", "liver function test", "lft",
            "kidney function test", "gfr", "egfr",
            # Lipid panel
            "lipid panel", "cholesterol", "ldl", "hdl", "triglycerides",
            # Cardiac
            "troponin", "bnp", "ecg", "electrocardiogram", "ekg",
            "echocardiogram", "echo", "stress test", "cardiac catheterization",
            # Imaging
            "chest x-ray", "chest xray", "chest radiograph", "x-ray", "xray",
            "mri", "ct scan", "cat scan", "ultrasound",
            "mammogram", "pet scan", "bone scan", "dexa scan",
            # Urinalysis & Other
            "urine test", "urinalysis", "urine culture",
            "tsh", "thyroid function test", "t3", "t4", "free t4",
            "inr", "pt", "ptt", "prothrombin time", "d-dimer",
            "biopsy", "cytology", "pathology", "endoscopy", "colonoscopy",
            "spirometry", "pulmonary function test", "pft",
            "lumbar puncture", "spinal tap",
        ),
        EntityType.DRUG: (
            # Respiratory
            "salbutamol", "albuterol", "cetirizine", "budesonide", "ipratropium",
            "fluticasone", "montelukast", "tiotropium", "theophylline",
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
            # GI
            "omeprazole", "pantoprazole", "lansoprazole", "ranitidine",
            "ondansetron", "metoclopramide", "loperamide", "bismuth",
            # Psychiatric / Neurological
            "sertraline", "fluoxetine", "escitalopram", "venlafaxine",
            "duloxetine", "amitriptyline", "gabapentin", "pregabalin",
            "carbamazepine", "valproate", "levetiracetam", "phenytoin",
            "diazepam", "lorazepam", "alprazolam", "zolpidem",
            "quetiapine", "risperidone", "olanzapine", "lithium",
            # Steroids & Allergy
            "prednisone", "prednisolone", "dexamethasone", "hydrocortisone",
            "methylprednisolone", "loratadine", "diphenhydramine", "fexofenadine",
            "levothyroxine", "methimazole", "allopurinol", "colchicine", "methotrexate",
        ),
    }

    PATTERNS: dict[EntityType, re.Pattern[str]] = {
        # Dosage: catches "500 mg", "2.5 mL", "100 mcg", "10,000 units", "1 g"
        EntityType.DOSAGE: re.compile(
            r"\b\d{1,5}(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|mL|units?|IU|mmol|mEq)\b",
            re.I,
        ),
        # Frequency
        EntityType.FREQUENCY: re.compile(
            r"\b(?:"
            r"(?:once|twice|thrice)\s+(?:a|per)\s+(?:day|daily|week|weekly)|"
            r"(?:every|q)\s*\d+\s*(?:h(?:ours?)?|min(?:utes?)?)|"
            r"(?:one|two|three|four)\s+times?\s+(?:a\s+)?(?:day|daily|week|weekly)|"
            r"(?:once|twice|three times)\s+daily|"
            r"(?:b\.?i\.?d\.?|t\.?i\.?d\.?|q\.?i\.?d\.?|q\.?d\.?|p\.?r\.?n\.?|"
            r"q\.?h\.?s\.?|a\.?c\.?|p\.?c\.?|stat|as needed|at bedtime|"
            r"in the morning|at night|before meals?|after meals?|with food)"
            r")\b",
            re.I,
        ),
        # Route
        EntityType.ROUTE: re.compile(
            r"\b(?:oral|orally|inhaler|inhalation|sublingual|topical|intravenous|iv|im|intramuscular|subcutaneous|subq)\b",
            re.I,
        ),
        # Duration: "for 5 days", "since 2 weeks", "for 3 months", "past 2 years", "yesterday"
        EntityType.DURATION: re.compile(
            r"\b(?:"
            r"(?:for|since|past|last|over the past|over the last|x)\s*\d+\s*(?:day|days|week|weeks|month|months|year|years)|"
            r"yesterday|today|since Monday|since yesterday"
            r")\b",
            re.I,
        ),
    }

    NEGATION_PREFIXES = (
        r"\b(?:no|not|denies|denied|without|negative for|free of|never had|ruled out|neither|nor|"
        r"not experiencing|no signs of|haven't had|have not had|did not have|zero)\b"
    )

    QUESTION_MARKERS = (
        r"\b(?:any|do you have|have you had|are you having|did you experience|is there any)\b"
    )

    def __init__(self) -> None:
        self._term_patterns: dict[EntityType, re.Pattern[str]] = {
            entity_type: re.compile(
                r"\b(?:" + "|".join(map(re.escape, sorted(terms, key=len, reverse=True))) + r")\b",
                re.I,
            )
            for entity_type, terms in self.TERMS.items()
        }

    def extract(self, turns: Iterable[TranscriptTurn]) -> list[ClinicalEntity]:
        output: list[ClinicalEntity] = []
        turn_list = list(turns)

        for turn in turn_list:
            # Term-based extraction (lexicon lookup)
            for entity_type, pattern in self._term_patterns.items():
                output.extend(
                    self._from_matches(turn, entity_type, pattern.finditer(turn.text), 0.88)
                )
            # Pattern-based extraction (regex)
            for entity_type, pattern in self.PATTERNS.items():
                output.extend(
                    self._from_matches(turn, entity_type, pattern.finditer(turn.text), 0.80)
                )

        return self._deduplicate_and_filter(output)

    def _determine_assertion(
        self, text: str, match_start: int, match_end: int, entity_type: EntityType, turn: TranscriptTurn
    ) -> str:
        """Context-aware clinical assertion classification."""
        if entity_type not in (EntityType.SYMPTOM, EntityType.DIAGNOSIS, EntityType.TEST):
            return "positive"

        # Extract sentence around match
        before = text[:match_start]
        after = text[match_end:]
        pre_words = before.split()[-8:]
        pre_context = " ".join(pre_words).lower()
        post_words = after.split()[:8]
        post_context = " ".join(post_words).lower()

        # Check explicit negation
        # e.g., "no chest pain or confusion", "denies chest pain", "without chest pain"
        if re.search(self.NEGATION_PREFIXES, pre_context):
            return "denied"
        if re.search(r"\b(?:denied|is absent|was ruled out|negative)\b", post_context):
            return "denied"

        # Check if asked as question by clinician without positive affirmation
        speaker_val = (turn.speaker.value if hasattr(turn.speaker, "value") else str(turn.speaker)).lower()
        if speaker_val == "clinician" and ("?" in text or re.search(self.QUESTION_MARKERS, pre_context)):
            return "uncertain"

        # Check if historical
        if re.search(r"\b(?:history of|previously had|in the past|past medical history)\b", pre_context):
            return "historical"

        return "positive"

    def _from_matches(
        self,
        turn: TranscriptTurn,
        entity_type: EntityType,
        matches: Iterable[re.Match[str]],
        score: float,
    ) -> list[ClinicalEntity]:
        entities: list[ClinicalEntity] = []
        for m in matches:
            assertion = self._determine_assertion(turn.text, m.start(), m.end(), entity_type, turn)
            entities.append(
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
                    assertion=assertion,
                )
            )
        return entities

    @staticmethod
    def _deduplicate_and_filter(entities: list[ClinicalEntity]) -> list[ClinicalEntity]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[ClinicalEntity] = []
        for e in entities:
            key = (e.provenance.turn_id, e.type.value, e.text.lower())
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        return deduped


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
                raw_label = item.get("entity_group", "").lower().replace("-", "_")
                label = raw_label[2:] if raw_label.startswith(("b_", "i_")) else raw_label
                try:
                    entity_type = EntityType(label)
                except ValueError:
                    continue
                output.append(
                    ClinicalEntity(
                        entity_id=str(uuid4()),
                        type=entity_type,
                        text=item["word"],
                        confidence=float(item["score"]),
                        provenance=Provenance(
                            turn_id=turn.turn_id,
                            start_char=int(item["start"]),
                            end_char=int(item["end"]),
                            source_text=turn.text,
                        ),
                        assertion="positive",
                    )
                )
        return output


def get_extractor() -> Extractor:
    model_id = os.getenv("MEDISCRIBE_NER_MODEL")
    return TransformersExtractor(model_id) if model_id else RuleBasedExtractor()
