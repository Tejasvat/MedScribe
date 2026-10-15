from __future__ import annotations

from collections import defaultdict
from uuid import uuid4
from .schemas import ClinicalEntity, EntityType, Medication, SafetyAlert, SoapNote, TranscriptTurn


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

    # Respiratory
    "albuterol": ("435", "albuterol"),
    "ventolin": ("435", "albuterol"),
    "proair": ("435", "albuterol"),
    "fluticasone": ("41126", "fluticasone"),
    "flovent": ("41126", "fluticasone"),
    "montelukast": ("88249", "montelukast"),
    "singulair": ("88249", "montelukast"),

    # Corticosteroids
    "prednisone": ("8640", "prednisone"),
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
        "Concurrent warfarin and aspirin markedly elevates major gastrointestinal and intracerebral bleeding risk. Co-prescribing requires strict clinical indication."
    ),
    frozenset(("warfarin", "ibuprofen")): (
        "high",
        "NSAIDs (ibuprofen) displace warfarin from protein binding and induce gastric mucosal erosion, creating high gastrointestinal hemorrhage risk."
    ),
    frozenset(("warfarin", "ciprofloxacin")): (
        "high",
        "Ciprofloxacin inhibits CYP1A2 and CYP3A4, significantly elevating warfarin bioavailability and INR. Prothrombin time monitoring strongly advised."
    ),
    frozenset(("clopidogrel", "omeprazole")): (
        "moderate",
        "Omeprazole inhibits CYP2C19-mediated activation of clopidogrel, significantly blunting its antiplatelet effect. Consider pantoprazole as an alternative."
    ),
    frozenset(("apixaban", "aspirin")): (
        "high",
        "Dual therapy with direct oral anticoagulant (apixaban) and aspirin substantially heightens severe bleeding risk. Verify indication."
    ),
    frozenset(("rivaroxaban", "aspirin")): (
        "high",
        "Concurrent rivaroxaban and aspirin increases major bleed rate without additional thrombotic benefit in most outpatients."
    ),

    # Cardiovascular / Renin-Angiotensin interactions
    frozenset(("lisinopril", "spironolactone")): (
        "high",
        "Concurrent ACE inhibitor and potassium-sparing diuretic creates critical risk of life-threatening hyperkalemia. Baseline electrolytes and renal function required."
    ),
    frozenset(("lisinopril", "ibuprofen")): (
        "moderate",
        "NSAIDs impair renal prostaglandins, blunting the antihypertensive effect of lisinopril and precipitously deteriorating glomerular filtration."
    ),
    frozenset(("losartan", "spironolactone")): (
        "high",
        "Angiotensin receptor blocker plus spironolactone increases severe hyperkalemia risk; monitor serum potassium regularly."
    ),
    frozenset(("digoxin", "amiodarone")): (
        "high",
        "Amiodarone inhibits P-glycoprotein, reducing digoxin renal clearance by ~50%. Halve digoxin dosage and monitor serum concentrations closely."
    ),
    frozenset(("metoprolol", "diltiazem")): (
        "moderate",
        "Co-administration of beta-blocker and non-dihydropyridine calcium channel blocker can precipitate profound bradycardia or heart block."
    ),

    # Statin interactions
    frozenset(("atorvastatin", "erythromycin")): (
        "high",
        "Erythromycin strongly inhibits CYP3A4 metabolism of atorvastatin, dramatically elevating blood levels and risk of severe rhabdomyolysis."
    ),
    frozenset(("simvastatin", "amiodarone")): (
        "high",
        "Amiodarone inhibits CYP3A4-mediated simvastatin clearance. Simvastatin dose should not exceed 20 mg daily to prevent myopathy."
    ),

    # Serotonin / CNS interactions
    frozenset(("tramadol", "sertraline")): (
        "high",
        "Combined serotonergic activity increases risk of life-threatening serotonin syndrome (hyperreflexia, clonus, autonomic instability)."
    ),
    frozenset(("tramadol", "fluoxetine")): (
        "high",
        "Fluoxetine potent CYP2D6 inhibition elevates tramadol levels while increasing serotonergic toxicity."
    ),
    frozenset(("sertraline", "ibuprofen")): (
        "moderate",
        "SSRIs diminish platelet serotonin uptake; combined with NSAIDs, upper GI ulcer and bleed risk increases 3- to 6-fold."
    ),
    frozenset(("sertraline", "aspirin")): (
        "moderate",
        "Concurrent SSRI and antiplatelet agent increases mucosal bleeding liability. Gastroprotective co-therapy may be indicated."
    ),

    # Musculoskeletal & Tendon toxicity
    frozenset(("ciprofloxacin", "prednisone")): (
        "high",
        "Fluoroquinolone combined with systemic corticosteroid drastically increases risk of severe tendinitis and Achilles tendon rupture, especially in older adults."
    ),
    frozenset(("levofloxacin", "prednisone")): (
        "high",
        "Concomitant levofloxacin and corticosteroid therapy synergistically escalates tendon rupture risk."
    ),
}


def normalize_medications(entities: list[ClinicalEntity]) -> list[Medication]:
    """Normalize drug mentions against the local RxNorm vocabulary."""
    meds = []
    for entity in entities:
        if entity.type != EntityType.DRUG:
            continue
        key = entity.text.lower().strip()
        match = RXNORM_LOCAL.get(key)
        
        # Also try single-word match if compound string
        if not match and " " in key:
            for word in key.split():
                if word in RXNORM_LOCAL:
                    match = RXNORM_LOCAL[word]
                    break

        meds.append(
            Medication(
                entity_id=entity.entity_id,
                mention=entity.text,
                rxcui=match[0] if match else None,
                normalized_name=match[1] if match else key,
                normalization_confidence=0.98 if match else 0.50,
            )
        )
    return meds


def safety_alerts(meds: list[Medication]) -> list[SafetyAlert]:
    """Generate drug-drug interaction and duplicate therapy alerts."""
    alerts: list[SafetyAlert] = []
    groups: dict[str, list[Medication]] = defaultdict(list)

    for med in meds:
        name = med.normalized_name or med.mention.lower()
        groups[name.lower()].append(med)

    # 1. Duplicate therapy detection
    for name, same in groups.items():
        if len(same) > 1:
            alerts.append(
                SafetyAlert(
                    alert_id=str(uuid4()),
                    severity="moderate",
                    category="duplicate_therapy",
                    message=(
                        f"Duplicate mention detected: '{name.title()}' appears {len(same)} times in the encounter. "
                        "Verify whether this represents an intended continuation, dose modification, or unintended duplication."
                    ),
                    medication_entity_ids=[m.entity_id for m in same],
                )
            )

    # 2. Drug-drug interactions from DDInter / DrugBank knowledge base
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


def draft_soap(turns: list[TranscriptTurn], entities: list[ClinicalEntity]) -> SoapNote:
    """Generate a structured SOAP note from segmented turns and extracted clinical entities."""
    patient_turns = [t.text for t in turns if t.speaker.value == "patient"]
    clinician_turns = [t.text for t in turns if t.speaker.value == "clinician"]

    by_type: dict[EntityType, list[str]] = defaultdict(list)
    for entity in entities:
        by_type[entity.type].append(entity.text)

    symptoms = sorted(set(by_type[EntityType.SYMPTOM]))
    adverse = sorted(set(by_type[EntityType.ADVERSE_EVENT]))
    tests = sorted(set(by_type[EntityType.TEST]))
    drugs = sorted(set(by_type[EntityType.DRUG]))
    dosages = sorted(set(by_type[EntityType.DOSAGE]))
    durations = sorted(set(by_type[EntityType.DURATION]))

    # Subjective
    subjective_lines = []
    if symptoms:
        subjective_lines.append(f"Chief Complaints / Reported Symptoms: {', '.join(symptoms)}")
    if durations:
        subjective_lines.append(f"Duration of complaints: {', '.join(durations)}")
    if adverse:
        subjective_lines.append(f"Adverse reactions reported: {', '.join(adverse)}")
    if not subjective_lines:
        subjective_lines = patient_turns or ["No subjective patient complaints explicitly extracted."]

    # Objective
    objective_lines = []
    if tests:
        objective_lines.append(f"Diagnostic studies & lab orders: {', '.join(tests)}")
    if not objective_lines:
        objective_lines = ["Vital signs and lab reports reviewed per encounter record."]

    # Assessment
    assessment_lines = []
    if symptoms:
        assessment_lines.append(f"Clinical presentation consistent with acute symptomatic episode ({', '.join(symptoms[:3])}).")
    if adverse:
        assessment_lines.append(f"Potential adverse effect to be monitored: {', '.join(adverse)}.")
    if not assessment_lines:
        assessment_lines = ["Clinical documentation assistive note under physician review."]

    # Plan
    plan_lines = []
    if drugs:
        med_summary = []
        for d in drugs:
            med_summary.append(d.title())
        plan_lines.append(f"Medication regimen: {', '.join(med_summary)}")
    if dosages:
        plan_lines.append(f"Dosage details: {', '.join(dosages)}")
    if tests:
        plan_lines.append(f"Pending tests & investigations: {', '.join(tests)}")
    if not plan_lines:
        plan_lines = clinician_turns or ["Follow-up as clinically indicated."]

    return SoapNote(
        subjective=subjective_lines,
        objective=objective_lines,
        assessment=assessment_lines,
        plan=plan_lines,
        disclaimer=(
            "AI-assisted documentation draft based on clinical NER. "
            "A licensed clinician must review, modify, and sign off before entry into the medical record."
        ),
    )
