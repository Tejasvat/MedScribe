git remote -v# MediScribe NER service

This service starts after speech-to-text. Send diarized transcript turns to its API and it returns:

- clinical entities: symptoms, medicines, doses, frequency, duration, tests, and adverse events
- confidence scores and exact source-turn provenance
- medication normalization and interaction / duplicate-therapy alerts
- a conservative, review-required SOAP-style draft
- a FHIR R4 Bundle suitable for a downstream EHR integration

It does not transcribe audio, diagnose, prescribe, or make medication changes. A clinician must review every output.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn mediscribe.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. A request example is in `examples/request.json`.

## Production model

The default `RuleBasedExtractor` runs without model downloads and makes the project immediately testable. For a trained BioBERT/ClinicalBERT token-classification model, set `MEDISCRIBE_NER_MODEL` to its local directory or Hugging Face model ID and install the ML extra:

```powershell
pip install -e ".[ml]"
$env:MEDISCRIBE_NER_MODEL = "./models/clinical-ner"
```

The model must use labels such as `B-DRUG`, `I-SYMPTOM`, `B-DOSAGE`, `B-FREQUENCY`, `B-DURATION`, `B-TEST`, and `B-ADVERSE_EVENT`. The API keeps provenance, normalization, safety checks, note drafting, and FHIR export independent of the model, so the model can be replaced without changing clients.

## Deployment notes

Run behind an authenticated TLS gateway. Store transcript text and output only in the clinic's approved database. The included API deliberately has no persistence or outbound requests. Its small local RxNorm mapping is a working development baseline; production should replace it with an approved local RxNorm terminology service or adapter.

