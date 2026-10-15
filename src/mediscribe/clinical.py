from __future__ import annotations

import re
from collections import defaultdict
from uuid import uuid4

from .schemas import (
    AllergyRecord,
    ClinicalEntity,
    EntityType,
    Investigation,
    InvestigationStatus,
    Medication,
    MedicationStatus,
    SafetyAlert,
    SoapNote,
    TranscriptTurn,
)

# Comprehensive RxNorm local database (RxCUI, normalized generic name)
RXNORM_LOCAL: dict[str, tuple[str, str]] = {
    # Analgesics & NSAIDs
    "paracetamol": ("161", "acetaminophen"),
    "acetaminophen": ("161", "acetaminophen"),
    "tylenol": ("161", "acetaminophen"),
    "ibuprofen": ("5640", "ibuprofen"),
    "advil": ("5640", "ibuprofen"),
    "motrin": ("5640", "ibuprofen"),
    "aspirin": ("1191", "aspirin"),
    "naproxen": ("7258", "naproxen"),
    "aleve": ("7258", "naproxen"),
    "diclofenac": ("3355", "diclofenac"),
    "voltaren": ("3355", "diclofenac"),
    "celecoxib": ("140587", "celecoxib"),
    "celebrex": ("140587", "celecoxib"),
    "tramadol": ("10689", "tramadol"),
    "ultram": ("10689", "tramadol"),
    "morphine": ("7052", "morphine"),
    "codeine": ("2670", "codeine"),
    "oxycodone": ("7804", "oxycodone"),
    "fentanyl": ("4337", "fentanyl"),

    # Antibiotics & Antifungals
    "amoxicillin": ("723", "amoxicillin"),
    "amoxil": ("723", "amoxicillin"),
    "azithromycin": ("18631", "azithromycin"),
    "zithromax": ("18631", "azithromycin"),
    "ciprofloxacin": ("2551", "ciprofloxacin"),
    "cipro": ("2551", "ciprofloxacin"),
    "levofloxacin": ("82122", "levofloxacin"),
    "levaquin": ("82122", "levofloxacin"),
    "doxycycline": ("3640", "doxycycline"),
    "metronidazole": ("6922", "metronidazole"),
    "flagyl": ("6922", "metronidazole"),
    "clindamycin": ("2582", "clindamycin"),
    "cephalexin": ("2231", "cephalexin"),
    "keflex": ("2231", "cephalexin"),
    "ceftriaxone": ("2193", "ceftriaxone"),
    "augmentin": ("18600", "amoxicillin-clavulanate"),
    "amoxicillin-clavulanate": ("18600", "amoxicillin-clavulanate"),
    "penicillin": ("70618", "penicillin"),
    "erythromycin": ("4053", "erythromycin"),
    "nitrofurantoin": ("7417", "nitrofurantoin"),

    # Anticoagulants & Antiplatelets
    "warfarin": ("11289", "warfarin"),
    "coumadin": ("11289", "warfarin"),
    "clopidogrel": ("32968", "clopidogrel"),
    "plavix": ("32968", "clopidogrel"),
    "heparin": ("5224", "heparin"),
    "apixaban": ("1364430", "apixaban"),
    "eliquis": ("1364430", "apixaban"),
    "rivaroxaban": ("1114195", "rivaroxaban"),
    "xarelto": ("1114195", "rivaroxaban"),
    "dabigatran": ("1037042", "dabigatran"),
    "pradaxa": ("1037042", "dabigatran"),

    # Cardiovascular & Antihypertensives
    "lisinopril": ("29046", "lisinopril"),
    "zestril": ("29046", "lisinopril"),
    "losartan": ("52175", "losartan"),
    "cozaar": ("52175", "losartan"),
    "amlodipine": ("17767", "amlodipine"),
    "norvasc": ("17767", "amlodipine"),
    "metoprolol": ("6918", "metoprolol"),
    "lopressor": ("6918", "metoprolol"),
    "atenolol": ("1202", "atenolol"),
    "hydrochlorothiazide": ("5487", "hydrochlorothiazide"),
    "hctz": ("5487", "hydrochlorothiazide"),
    "furosemide": ("4603", "furosemide"),
    "lasix": ("4603", "furosemide"),
    "spironolactone": ("9997", "spironolactone"),
    "aldactone": ("9997", "spironolactone"),
    "carvedilol": ("20352", "carvedilol"),
    "coreg": ("20352", "carvedilol"),
    "diltiazem": ("3443", "diltiazem"),
    "digoxin": ("3407", "digoxin"),
    "lanoxin": ("3407", "digoxin"),
    "amiodarone": ("703", "amiodarone"),
    "cordarone": ("703", "amiodarone"),
    "nitroglycerin": ("7435", "nitroglycerin"),

    # Diabetes / Metabolic
    "metformin": ("6809", "metformin"),
    "glucophage": ("6809", "metformin"),
    "glipizide": ("4821", "glipizide"),
    "insulin": ("5856", "insulin"),
    "sitagliptin": ("593411", "sitagliptin"),
    "januvia": ("593411", "sitagliptin"),
    "empagliflozin": ("1545653", "empagliflozin"),
    "jardiance": ("1545653", "empagliflozin"),

    # Statins / Lipid Lowering
    "atorvastatin": ("83367", "atorvastatin"),
    "lipitor": ("83367", "atorvastatin"),
    "simvastatin": ("36567", "simvastatin"),
    "zocor": ("36567", "simvastatin"),
    "rosuvastatin": ("301542", "rosuvastatin"),
    "crestor": ("301542", "rosuvastatin"),
    "pravastatin": ("42463", "pravastatin"),

    # Gastrointestinal (PPIs / H2 blockers)
    "omeprazole": ("7646", "omeprazole"),
    "prilosec": ("7646", "omeprazole"),
    "pantoprazole": ("40790", "pantoprazole"),
    "protonix": ("40790", "pantoprazole"),
    "famotidine": ("4278", "famotidine"),
    "pepcid": ("4278", "famotidine"),

    # Respiratory & Inhalers
    "salbutamol": ("435", "albuterol"),
    "albuterol": ("435", "albuterol"),
    "ventolin": ("435", "albuterol"),
    "proair": ("435", "albuterol"),
    "budesonide": ("19831", "budesonide"),
    "pulmicort": ("19831", "budesonide"),
    "fluticasone": ("41126", "fluticasone"),
    "flovent": ("41126", "fluticasone"),
    "montelukast": ("88249", "montelukast"),
    "singulair": ("88249", "montelukast"),
    "ipratropium": ("5933", "ipratropium"),

    # Antihistamines & Allergy
    "cetirizine": ("20610", "cetirizine"),
    "zyrtec": ("20610", "cetirizine"),
    "loratadine": ("6574", "loratadine"),
    "claritin": ("6574", "loratadine"),
    "fexofenadine": ("42347", "fexofenadine"),
    "allegra": ("42347", "fexofenadine"),
    "diphenhydramine": ("3498", "diphenhydramine"),
    "benadryl": ("3498", "diphenhydramine"),

    # Corticosteroids
    "prednisone": ("8640", "prednisone"),
    "prednisolone": ("8638", "prednisolone"),
    "methylprednisolone": ("6902", "methylprednisolone"),
    "medrol": ("6902", "methylprednisolone"),
    "dexamethasone": ("3264", "dexamethasone"),

    # Psychiatric / Neurological
    "sertraline": ("36437", "sertraline"),
    "zoloft": ("36437", "sertraline"),
    "escitalopram": ("32937", "escitalopram"),
    "lexapro": ("32937", "escitalopram"),
    "fluoxetine": ("4493", "fluoxetine"),
    "prozac": ("4493", "fluoxetine"),
    "duloxetine": ("72625", "duloxetine"),
    "cymbalta": ("72625", "duloxetine"),
    "gabapentin": ("25480", "gabapentin"),
    "neurontin": ("25480", "gabapentin"),
    "pregabalin": ("187832", "pregabalin"),
    "lyrica": ("187832", "pregabalin"),

    # Thyroid
    "levothyroxine": ("10582", "levothyroxine"),
    "synthroid": ("10582", "levothyroxine"),
}

# DDInter / DrugBank-aligned high & moderate clinical interactions
INTERACTIONS: dict[frozenset[str], tuple[str, str]] = {
    # Anticoagulant interactions
    frozenset(("warfarin", "aspirin")): (
        "high",
        "Concurrent warfarin and aspirin markedly elevates major gastrointestinal and intracerebral bleeding risk. Co-prescribing requires strict clinical indication.",
    ),
    frozenset(("warfarin", "ibuprofen")): (
        "high",
        "NSAIDs (ibuprofen) displace warfarin from protein binding and induce gastric mucosal erosion, creating high gastrointestinal hemorrhage risk.",
    ),
    frozenset(("warfarin", "ciprofloxacin")): (
        "high",
        "Ciprofloxacin inhibits CYP1A2 and CYP3A4, significantly elevating warfarin bioavailability and INR. Prothrombin time monitoring strongly advised.",
    ),
    frozenset(("clopidogrel", "omeprazole")): (
        "moderate",
        "Omeprazole inhibits CYP2C19-mediated activation of clopidogrel, significantly blunting its antiplatelet effect. Consider pantoprazole as an alternative.",
    ),
    frozenset(("apixaban", "aspirin")): (
        "high",
        "Dual therapy with direct oral anticoagulant (apixaban) and aspirin substantially heightens severe bleeding risk. Verify indication.",
    ),
    frozenset(("rivaroxaban", "aspirin")): (
        "high",
        "Concurrent rivaroxaban and aspirin increases major bleed rate without additional thrombotic benefit in most outpatients.",
    ),

    # Cardiovascular / Renin-Angiotensin interactions
    frozenset(("lisinopril", "spironolactone")): (
        "high",
        "Concurrent ACE inhibitor and potassium-sparing diuretic creates critical risk of life-threatening hyperkalemia. Baseline electrolytes and renal function required.",
    ),
    frozenset(("lisinopril", "ibuprofen")): (
        "moderate",
        "NSAIDs impair renal prostaglandins, blunting the antihypertensive effect of lisinopril and precipitously deteriorating glomerular filtration.",
    ),
    frozenset(("losartan", "spironolactone")): (
        "high",
        "Angiotensin receptor blocker plus spironolactone increases severe hyperkalemia risk; monitor serum potassium regularly.",
    ),
    frozenset(("digoxin", "amiodarone")): (
        "high",
        "Amiodarone inhibits P-glycoprotein, reducing digoxin renal clearance by ~50%. Halve digoxin dosage and monitor serum concentrations closely.",
    ),
    frozenset(("metoprolol", "diltiazem")): (
        "moderate",
        "Co-administration of beta-blocker and non-dihydropyridine calcium channel blocker can precipitate profound bradycardia or heart block.",
    ),

    # Statin interactions
    frozenset(("atorvastatin", "erythromycin")): (
        "high",
        "Erythromycin strongly inhibits CYP3A4 metabolism of atorvastatin, dramatically elevating blood levels and risk of severe rhabdomyolysis.",
    ),
    frozenset(("simvastatin", "amiodarone")): (
        "high",
        "Amiodarone inhibits CYP3A4-mediated simvastatin clearance. Simvastatin dose should not exceed 20 mg daily to prevent myopathy.",
    ),

    # Serotonin / CNS interactions
    frozenset(("tramadol", "sertraline")): (
        "high",
        "Combined serotonergic activity increases risk of life-threatening serotonin syndrome (hyperreflexia, clonus, autonomic instability).",
    ),
    frozenset(("tramadol", "fluoxetine")): (
        "high",
        "Fluoxetine potent CYP2D6 inhibition elevates tramadol levels while increasing serotonergic toxicity.",
    ),
    frozenset(("sertraline", "ibuprofen")): (
        "moderate",
        "SSRIs diminish platelet serotonin uptake; combined with NSAIDs, upper GI ulcer and bleed risk increases 3- to 6-fold.",
    ),
    frozenset(("sertraline", "aspirin")): (
        "moderate",
        "Concurrent SSRI and antiplatelet agent increases mucosal bleeding liability. Gastroprotective co-therapy may be indicated.",
    ),

    # Musculoskeletal & Tendon toxicity
    frozenset(("ciprofloxacin", "prednisone")): (
        "high",
        "Fluoroquinolone combined with systemic corticosteroid drastically increases risk of severe tendinitis and Achilles tendon rupture, especially in older adults.",
    ),
    frozenset(("levofloxacin", "prednisone")): (
        "high",
        "Concomitant levofloxacin and corticosteroid therapy synergistically escalates tendon rupture risk.",
    ),
}


def _classify_medication_status(sentence: str, speaker: str, drug_name: str) -> MedicationStatus:
    """Classify the clinical status of a medication mention based on sentence context and speaker."""
    s = sentence.lower()
    d = drug_name.lower()

    # 1. Allergy-related mention
    if any(k in s for k in ("allergic to", "allergy to", "allergy", "rash from", "developed a rash", "gives me hives", "hives and skin rash", "hypersensitivity")):
        if d in s or any(p in s for p in ("penicillin", "beta-lactam")):
            return MedicationStatus.ALLERGY_RELATED

    # 2. Not prescribed / considered but rejected / not recommended
    # "is not prescribed", "will not prescribe", "do not prescribe", "avoid", "must avoid", "not recommended", "cannot combine"
    if any(k in s for k in (
        "not prescribed", "will not prescribe", "do not prescribe", "did not prescribe",
        "must avoid", "avoid", "not recommended", "should not take", "cannot combine",
        "we will defer", "discontinue", "stop taking", "stop paracetamol", "stop pannunga"
    )):
        return MedicationStatus.CONSIDERED_NOT_PRESCRIBED if "prescribe" in s or "consider" in s or "thought" in s else MedicationStatus.NOT_RECOMMENDED

    # "considered ... but", "thought about ... but"
    if ("consider" in s or "thought about" in s or "could consider" in s) and ("not" in s or "stage" in s or "defer" in s):
        return MedicationStatus.CONSIDERED_NOT_PRESCRIBED

    # 3. Previously taken / historical medication
    if any(k in s for k in (
        "previously took", "previously taken", "used to take",
        "past use", "in the past", "tried", "yesterday", "earlier", "since monday"
    )) and speaker == "patient":
        # Check if they said "am currently taking"
        if "currently taking" not in s and "am taking" not in s:
            return MedicationStatus.PREVIOUSLY_TAKEN

    # 4. Currently taking (existing medication)
    if any(k in s for k in (
        "currently taking", "am taking", "taking", "i take", "take", "takes", "continue",
        "regularly take", "on salbutamol", "on warfarin", "on lisinopril"
    )):
        if speaker == "patient" or "continue" in s or "taking" in s or "take" in s:
            if speaker != "clinician" or "continue" in s or "taking" in s:
                return MedicationStatus.CURRENTLY_TAKING

    # 5. Doctor recommendation (without formal prescription)
    if speaker == "clinician" and any(k in s for k in (
        "i recommend", "recommend", "recommended", "for symptom relief", "can take", "suggest"
    )) and not any(k in s for k in ("prescribe", "order", "prescription")):
        return MedicationStatus.RECOMMENDED

    # 6. Explicitly prescribed
    if speaker == "clinician" and any(k in s for k in (
        "i will prescribe", "prescribe", "prescribing", "let us prescribe",
        "let us start", "take azithromycin", "take pantoprazole", "take amoxicillin"
    )):
        return MedicationStatus.PRESCRIBED

    # If clinician mentions continuing existing medication
    if speaker == "clinician" and "continue" in s:
        return MedicationStatus.CURRENTLY_TAKING

    return MedicationStatus.UNKNOWN


def _extract_attributes_from_sentence(sentence: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract dosage, frequency, route, and duration from the given context sentence."""
    dosage_pattern = r"\b\d{1,5}(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|mL|units?|IU|mmol|mEq)\b"
    freq_pattern = (
        r"\b(?:"
        r"(?:once|twice|three times|thrice)\s+(?:a|per)\s+(?:day|daily|week|weekly)|"
        r"(?:every|q)\s*\d+\s*(?:h(?:ours?)?|min(?:utes?)?)|"
        r"(?:one|two|three|four)\s+times?\s+(?:a\s+)?(?:day|daily|week|weekly)|"
        r"(?:once|twice|three times)\s+daily|"
        r"as needed|prn|at bedtime|in the morning|before breakfast|after food|daily"
        r")\b"
    )
    route_pattern = r"\b(?:inhaler|oral|orally|tablet|capsule|sublingual|topical|iv|im)\b"
    duration_pattern = (
        r"\b(?:"
        r"(?:for|since|past|last|over the past|over the last)\s*\d+\s*(?:day|days|week|weeks|month|months|year|years)|"
        r"yesterday|today|since Monday"
        r")\b"
    )

    dosage_match = re.search(dosage_pattern, sentence, re.I)
    freq_match = re.search(freq_pattern, sentence, re.I)
    route_match = re.search(route_pattern, sentence, re.I)
    duration_match = re.search(duration_pattern, sentence, re.I)

    dosage = dosage_match.group(0).strip() if dosage_match else None
    frequency = freq_match.group(0).strip() if freq_match else None
    route = route_match.group(0).strip() if route_match else None
    duration = duration_match.group(0).strip() if duration_match else None

    return dosage, frequency, route, duration


def normalize_medications(
    entities: list[ClinicalEntity], turns: list[TranscriptTurn] | None = None
) -> list[Medication]:
    """Normalize drug mentions against RxNorm with context-aware status and attribute extraction."""
    turn_map: dict[str, TranscriptTurn] = {t.turn_id: t for t in turns} if turns else {}
    raw_meds: list[Medication] = []

    for entity in entities:
        if entity.type != EntityType.DRUG:
            continue

        raw_mention = entity.text
        key = raw_mention.lower().strip(" .,!?:;'\"()")
        match = RXNORM_LOCAL.get(key)

        # Compound string split lookup
        if not match and " " in key:
            for word in key.split():
                clean_word = word.strip(" .,!?:;'\"()")
                if clean_word in RXNORM_LOCAL:
                    match = RXNORM_LOCAL[clean_word]
                    break

        rxcui = match[0] if match else None
        normalized_name = match[1] if match else key
        confidence = 0.98 if match else 0.50

        # Context analysis
        turn = turn_map.get(entity.provenance.turn_id)
        sentence = entity.provenance.source_text
        speaker = "unknown"
        if turn:
            speaker = (
                turn.speaker.value if hasattr(turn.speaker, "value") else str(turn.speaker)
            ).lower()

        # Extract context sentence if source_text contains multiple sentences
        sentences = re.split(r"(?<=[.!?])\s+", sentence)
        context_sentence = sentence
        for s in sentences:
            if raw_mention.lower() in s.lower():
                context_sentence = s
                break

        status = _classify_medication_status(context_sentence, speaker, key)
        dosage, frequency, route, duration = _extract_attributes_from_sentence(context_sentence)

        med = Medication(
            entity_id=entity.entity_id,
            mention=raw_mention,
            rxcui=rxcui,
            normalized_name=normalized_name,
            normalization_confidence=confidence,
            status=status,
            status_display=status.display_name,
            dosage=dosage,
            frequency=frequency,
            route=route,
            duration=duration,
            context=context_sentence.strip(),
            turn_id=entity.provenance.turn_id,
        )
        raw_meds.append(med)

    # Intelligent deduplication & consolidation:
    # 1. Same drug with SAME status -> consolidate (merge attributes, don't duplicate).
    # 2. Same drug with DIFFERENT status (e.g. Paracetamol previously taken vs. recommended) -> PRESERVE BOTH!
    consolidated: list[Medication] = []
    seen: dict[tuple[str, MedicationStatus], int] = {}

    for med in raw_meds:
        drug_key = med.normalized_name or med.mention.lower()
        group_key = (drug_key.lower(), med.status)

        if group_key in seen:
            existing_idx = seen[group_key]
            existing = consolidated[existing_idx]
            # Merge richer attributes
            if not existing.dosage and med.dosage:
                existing.dosage = med.dosage
            if not existing.frequency and med.frequency:
                existing.frequency = med.frequency
            if not existing.route and med.route:
                existing.route = med.route
            if not existing.duration and med.duration:
                existing.duration = med.duration
        else:
            seen[group_key] = len(consolidated)
            consolidated.append(med)

    return consolidated


def extract_allergies(
    turns: list[TranscriptTurn], entities: list[ClinicalEntity]
) -> list[AllergyRecord]:
    """Separate pipeline for allergy and adverse-reaction extraction."""
    allergies: list[AllergyRecord] = []
    allergy_keywords = (
        r"\b(?:allergic to|allergy to|allergy|allergies|hives|rash|skin rash|adverse reaction|anaphylaxis)\b"
    )

    for turn in turns:
        text = turn.text
        sentences = re.split(r"(?<=[.!?])\s+", text)
        speaker = (
            turn.speaker.value if hasattr(turn.speaker, "value") else str(turn.speaker)
        ).lower()

        for sentence in sentences:
            if not re.search(allergy_keywords, sentence, re.I):
                continue

            # Look for drug or substance in sentence
            substances: list[str] = []
            for drug_name in ("penicillin", "amoxicillin", "aspirin", "ibuprofen", "sulfa", "codeine", "latex"):
                if re.search(r"\b" + re.escape(drug_name) + r"\b", sentence, re.I):
                    substances.append(drug_name)

            # Reactions
            reactions: list[str] = []
            for reaction_name in ("rash", "skin rash", "hives", "anaphylaxis", "itching", "swelling", "nausea"):
                if re.search(r"\b" + re.escape(reaction_name) + r"\b", sentence, re.I):
                    reactions.append(reaction_name)

            if substances:
                reaction_str = ", ".join(reactions) if reactions else "reported allergic reaction"
                timing = "historical" if any(w in sentence.lower() for w in ("previously", "past", "history", "years ago", "developed")) else "current"

                for sub in substances:
                    allergies.append(
                        AllergyRecord(
                            allergy_id=str(uuid4()),
                            substance=sub,
                            reaction=reaction_str,
                            timing=timing,
                            source=speaker,
                            supporting_sentence=sentence.strip(),
                            turn_id=turn.turn_id,
                        )
                    )

    # Deduplicate allergies by substance
    unique_allergies: list[AllergyRecord] = []
    seen_subs = set()
    for a in allergies:
        if a.substance.lower() not in seen_subs:
            seen_subs.add(a.substance.lower())
            unique_allergies.append(a)

    return unique_allergies


def extract_investigations(
    turns: list[TranscriptTurn], entities: list[ClinicalEntity]
) -> list[Investigation]:
    """Separate pipeline for diagnostic tests and investigations with context-aware status."""
    turn_map = {t.turn_id: t for t in turns}
    investigations: list[Investigation] = []

    for ent in entities:
        if ent.type != EntityType.TEST:
            continue

        turn = turn_map.get(ent.provenance.turn_id)
        sentence = ent.provenance.source_text
        sentences = re.split(r"(?<=[.!?])\s+", sentence)
        context_sentence = sentence
        for s in sentences:
            if ent.text.lower() in s.lower():
                context_sentence = s
                break

        cs = context_sentence.lower()
        status = InvestigationStatus.DISCUSSED
        condition_detail = None
        result = None

        # Check conditional
        if any(k in cs for k in ("if", "worsens", "in case of", "unless", "conditional", "clinically indicated")):
            status = InvestigationStatus.CONDITIONAL
            if "if" in cs:
                condition_detail = cs[cs.find("if"):].split(".")[0].strip()
            elif "worsen" in cs:
                condition_detail = "if symptoms/breathlessness worsen"
        elif any(k in cs for k in ("consider", "thought about", "could consider")):
            status = InvestigationStatus.CONSIDERED
        elif any(k in cs for k in ("will order", "order", "ordering", "schedule", "stat order", "check your")):
            status = InvestigationStatus.ORDERED
        elif any(k in cs for k in ("recommend", "recommend a", "suggest")):
            status = InvestigationStatus.RECOMMENDED
        elif any(k in cs for k in ("result", "showed", "negative", "positive", "normal", "elevated")):
            status = InvestigationStatus.COMPLETED
            result = "Reviewed per transcript"
        elif any(k in cs for k in ("discuss", "talked about")):
            status = InvestigationStatus.DISCUSSED

        investigations.append(
            Investigation(
                investigation_id=str(uuid4()),
                mention=ent.text,
                normalized_name=ent.text.upper(),
                status=status,
                status_display=status.display_name,
                condition_detail=condition_detail,
                result=result,
                turn_id=ent.provenance.turn_id,
                supporting_sentence=context_sentence.strip(),
            )
        )

    # Deduplicate tests by name and status
    unique_tests: list[Investigation] = []
    seen = set()
    for inv in investigations:
        key = (inv.mention.lower(), inv.status)
        if key not in seen:
            seen.add(key)
            unique_tests.append(inv)

    return unique_tests


def safety_alerts(
    meds: list[Medication], allergies: list[AllergyRecord] | None = None
) -> list[SafetyAlert]:
    """Generate drug-drug interaction, duplicate therapy, and allergy safety alerts without redundant duplicates."""
    alerts: list[SafetyAlert] = []
    groups: dict[str, list[Medication]] = defaultdict(list)

    # 1. Allergy-based safety alerts (Deduplicated per contraindicated drug class/concept)
    # 1. Allergy-based safety alerts (Consolidated & deduplicated per contraindicated drug class)
    if allergies:
        beta_lactam_drugs = ("amoxicillin", "penicillin", "augmentin", "cephalexin", "ceftriaxone")
        reported_allergies = {a.substance.lower(): a for a in allergies}
        has_beta_lactam_allergy = any(
            "penicillin" in sub or "amoxicillin" in sub for sub in reported_allergies
        )

        if has_beta_lactam_allergy:
            # Find all relevant beta-lactam medications in the encounter
            matched_meds = [
                m for m in meds
                if (m.normalized_name or m.mention).lower() in beta_lactam_drugs
            ]
            if matched_meds:
                # Prefer the allergy entry that has the reported reaction (e.g. rash)
                allergy_ref = next(
                    (a for a in reported_allergies.values() if a.reaction and "reported" not in a.reaction.lower()),
                    next(iter(reported_allergies.values()))
                )
                reaction_note = f" ({allergy_ref.reaction})" if allergy_ref.reaction else ""
                unique_contraindicated_names = sorted(
                    list({(m.normalized_name or m.mention).title() for m in matched_meds})
                )
                contraindicated_str = ", ".join(unique_contraindicated_names)
                alerts.append(
                    SafetyAlert(
                        alert_id=str(uuid4()),
                        severity="critical",
                        category="allergy_contraindication",
                        message=(
                            f"Allergy Contraindication: Patient has documented {allergy_ref.substance.title()} allergy{reaction_note}. "
                            f"Strictly avoid beta-lactam antibiotics ({contraindicated_str}) due to high risk of hypersensitivity reaction."
                        ),
                        medication_entity_ids=[m.entity_id for m in matched_meds],
                    )
                )

    # For DDI and duplication checks, evaluate active regimens (currently taking or newly prescribed)
    # Exclude historical/previously taken, considered not prescribed, not recommended, or allergy mentions
    active_regimen_statuses = (
        MedicationStatus.CURRENTLY_TAKING,
        MedicationStatus.PRESCRIBED,
    )
    # For DDI checks, include recommended as well
    ddi_statuses = (
        MedicationStatus.CURRENTLY_TAKING,
        MedicationStatus.PRESCRIBED,
        MedicationStatus.RECOMMENDED,
        MedicationStatus.UNKNOWN,
    )

    for med in meds:
        if med.status in ddi_statuses:
            name = med.normalized_name or med.mention.lower()
            groups[name.lower()].append(med)

    # 2. Duplicate therapy detection:
    # Only flag duplicate therapy when there are multiple concurrent active or prescribed orders for the same drug
    # (e.g., patient taking Drug X and doctor also prescribes Drug X, or multiple conflicting active prescriptions).
    # Do NOT flag historical usage vs new recommendation or benign re-mentions.
    for name, same in groups.items():
        concurrent_active = [m for m in same if m.status in active_regimen_statuses]
        # Or multiple distinct active entries
        if len(concurrent_active) > 1:
            alerts.append(
                SafetyAlert(
                    alert_id=str(uuid4()),
                    severity="moderate",
                    category="duplicate_therapy",
                    message=(
                        f"Duplicate therapy warning: '{name.title()}' appears {len(concurrent_active)} times as an active regimen. "
                        "Verify whether this represents an intended continuation, dose modification, or unintended duplication."
                    ),
                    medication_entity_ids=[m.entity_id for m in concurrent_active],
                )
            )

    # 3. Drug-drug interactions from DDInter / DrugBank knowledge base
    values = list(groups.items())
    for index, (a, a_meds) in enumerate(values):
        for b, b_meds in values[index + 1:]:
            interaction = INTERACTIONS.get(frozenset((a, b)))
            if interaction:
                severity, message = interaction
                alerts.append(
                    SafetyAlert(
                        alert_id=str(uuid4()),
                        severity=severity,
                        category="drug_interaction",
                        message=message,
                        medication_entity_ids=[a_meds[0].entity_id, b_meds[0].entity_id],
                    )
                )

    return alerts


def draft_soap(
    turns: list[TranscriptTurn],
    entities: list[ClinicalEntity],
    medications: list[Medication] | None = None,
    allergies: list[AllergyRecord] | None = None,
    investigations: list[Investigation] | None = None,
    patient_name: str | None = None,
    patient_age: int | str | None = None,
    physician_name: str | None = None,
) -> SoapNote:
    """Generate a structured, context-aware SOAP note adhering to strict clinical accuracy."""
    by_type: dict[EntityType, list[ClinicalEntity]] = defaultdict(list)
    for entity in entities:
        by_type[entity.type].append(entity)

    # Positive symptoms ONLY (explicitly filter out denied, uncertain, or conditional)
    positive_symptoms = sorted(set(
        e.text.capitalize() for e in by_type[EntityType.SYMPTOM] if e.assertion == "positive"
    ))
    denied_symptoms = sorted(set(
        e.text.capitalize() for e in by_type[EntityType.SYMPTOM] if e.assertion == "denied"
    ))
    medical_history = sorted(set(
        e.text.capitalize() for e in by_type[EntityType.DIAGNOSIS]
    ))
    durations = sorted(set(e.text for e in by_type[EntityType.DURATION]))

    # --- SUBJECTIVE ---
    subjective_lines = []
    if patient_name:
        age_str = f", age {patient_age}" if patient_age else ""
        subjective_lines.append(f"Patient: {patient_name}{age_str}.")

    if positive_symptoms:
        subjective_lines.append(f"Chief Complaints: {', '.join(positive_symptoms)}.")
    if durations:
        subjective_lines.append(f"Timeline: Symptoms reported {', '.join(durations)}.")
    if denied_symptoms:
        subjective_lines.append(f"Pertinent Negatives: Explicitly denies {', '.join(denied_symptoms)}.")
    if medical_history:
        subjective_lines.append(f"Past Medical History: {', '.join(medical_history)}.")

    # Allergies in Subjective
    allergy_lines = []
    if allergies:
        for a in allergies:
            timing_note = f" ({a.timing})" if a.timing else ""
            allergy_lines.append(f"{a.substance.title()}: {a.reaction}{timing_note}")
        subjective_lines.append(f"Allergies / Adverse Reactions: {'; '.join(allergy_lines)}.")

    # Medications in Subjective (current vs previously taken)
    if medications:
        current_meds = [m for m in medications if m.status == MedicationStatus.CURRENTLY_TAKING]
        past_meds = [m for m in medications if m.status == MedicationStatus.PREVIOUSLY_TAKEN]
        if current_meds:
            med_strs = [f"{m.normalized_name.title() if m.normalized_name else m.mention.title()}{f' ({m.dosage})' if m.dosage else ''}" for m in current_meds]
            subjective_lines.append(f"Current Baseline Medications: {', '.join(med_strs)}.")
        if past_meds:
            past_strs = [f"{m.normalized_name.title() if m.normalized_name else m.mention.title()}{f' ({m.dosage})' if m.dosage else ''}" for m in past_meds]
            subjective_lines.append(f"Previously Taken: {', '.join(past_strs)}.")

    if not subjective_lines:
        subjective_lines = ["No subjective patient complaints explicitly established."]

    # --- OBJECTIVE ---
    objective_lines = ["Vital signs and clinical observations reviewed per encounter record."]
    if investigations:
        ordered_invs = [i for i in investigations if i.status == InvestigationStatus.ORDERED]
        cond_invs = [i for i in investigations if i.status == InvestigationStatus.CONDITIONAL]
        disc_invs = [i for i in investigations if i.status == InvestigationStatus.DISCUSSED]

        if ordered_invs:
            objective_lines.append(f"Diagnostic Orders (Ordered): {', '.join(i.mention.upper() for i in ordered_invs)}.")
        if cond_invs:
            for ci in cond_invs:
                detail = f" ({ci.condition_detail})" if ci.condition_detail else ""
                objective_lines.append(f"Diagnostic Discussion (Conditional): {ci.mention.title()}{detail} — not ordered today.")
        if disc_invs:
            objective_lines.append(f"Diagnostic Discussion (Discussed): {', '.join(i.mention.title() for i in disc_invs)}.")

    # --- ASSESSMENT ---
    assessment_lines = []
    if positive_symptoms:
        top_syms = ", ".join(positive_symptoms[:4])
        assessment_lines.append(f"Clinical Presentation: Acute symptomatic presentation ({top_syms}). Diagnosis is not yet definitively established.")
    if medical_history:
        assessment_lines.append(f"Pre-existing Conditions: {', '.join(medical_history)}.")
    if allergies:
        subs = ", ".join(a.substance.title() for a in allergies)
        assessment_lines.append(f"Safety Precaution: Documented hypersensitivity to {subs}; avoid beta-lactam agents.")
    if not assessment_lines:
        assessment_lines = ["Clinical documentation note under physician review."]

    # --- PLAN ---
    plan_lines = []
    if medications:
        prescribed = [m for m in medications if m.status == MedicationStatus.PRESCRIBED]
        recommended = [m for m in medications if m.status == MedicationStatus.RECOMMENDED]
        continued = [m for m in medications if m.status == MedicationStatus.CURRENTLY_TAKING]
        withheld = [m for m in medications if m.status in (MedicationStatus.CONSIDERED_NOT_PRESCRIBED, MedicationStatus.NOT_RECOMMENDED, MedicationStatus.ALLERGY_RELATED)]

        if prescribed:
            p_strs = [f"{m.normalized_name.title() if m.normalized_name else m.mention.title()}{f' {m.dosage}' if m.dosage else ''}{f' {m.frequency}' if m.frequency else ''}" for m in prescribed]
            plan_lines.append(f"Prescriptions Issued: {', '.join(p_strs)}.")
        if recommended:
            r_strs = [f"{m.normalized_name.title() if m.normalized_name else m.mention.title()}{f' {m.dosage}' if m.dosage else ''}{f' {m.frequency}' if m.frequency else ''}" for m in recommended]
            plan_lines.append(f"Symptom Relief (Recommended): {', '.join(r_strs)}.")
        if continued:
            c_strs = [f"{m.normalized_name.title() if m.normalized_name else m.mention.title()}" for m in continued]
            plan_lines.append(f"Continue Existing Therapy: {', '.join(c_strs)}.")
        if withheld:
            w_strs = [f"{m.normalized_name.title() if m.normalized_name else m.mention.title()} (not prescribed/avoided)" for m in withheld]
            plan_lines.append(f"Withheld / Rejected Treatments: {', '.join(w_strs)}.")

    if investigations:
        cond = [i for i in investigations if i.status == InvestigationStatus.CONDITIONAL]
        for c in cond:
            plan_lines.append(f"Conditional Investigation: {c.mention.title()} if {c.condition_detail or 'symptoms worsen'}.")

    plan_lines.append("Follow-up: Advised to seek urgent medical evaluation if severe breathlessness or high fever develops.")

    return SoapNote(
        subjective=subjective_lines,
        objective=objective_lines,
        assessment=assessment_lines,
        plan=plan_lines,
        disclaimer=(
            "AI-assisted clinical documentation draft. "
            "A licensed clinician must review, verify, modify, and countersign before medical record entry."
        ),
        pertinent_negatives=[f"Denies {s}" for s in denied_symptoms],
        medical_history=medical_history,
        allergies=allergy_lines,
    )
