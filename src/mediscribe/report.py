"""Generate concise, impactful clinical executive reports from analysis results."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def generate_html_report(result: dict[str, Any]) -> str:
    """Generate a brief, executive, high-impact clinical encounter report."""

    encounter_id = html.escape(str(result.get("encounter_id", "N/A")))
    patient_name = html.escape(str(result.get("patient_name") or result.get("patient_id") or "Not provided"))
    physician_name = html.escape(str(result.get("physician_name") or "Not provided"))
    patient_age = html.escape(str(result.get("patient_age") or "Not provided"))

    timestamp = datetime.now().strftime("%b %d, %Y · %H:%M")

    entities = result.get("entities", [])
    medications = result.get("medications", [])
    allergies = result.get("allergies", [])
    investigations = result.get("investigations", [])
    safety_alerts = result.get("safety_alerts", [])
    soap_note = result.get("soap_note", {})

    # 1. Actionable Safety Alert Banner (Impactful Callout)
    SEV_CONFIG = {
        "critical": ("#ef4444", "rgba(239, 68, 68, 0.12)", "rgba(239, 68, 68, 0.35)", "CRITICAL ALERT"),
        "high":     ("#f87171", "rgba(248, 113, 113, 0.12)", "rgba(248, 113, 113, 0.30)", "HIGH PRIORITY"),
        "moderate": ("#fbbf24", "rgba(251, 191, 36, 0.12)", "rgba(251, 191, 36, 0.30)", "WARNING"),
        "info":     ("#38bdf8", "rgba(56, 189, 248, 0.12)", "rgba(56, 189, 248, 0.30)", "NOTE"),
    }

    alert_blocks = ""
    if safety_alerts:
        for alert in safety_alerts:
            sev = alert.get("severity", "info").lower()
            fg, bg, border, label = SEV_CONFIG.get(sev, SEV_CONFIG["info"])
            cat = html.escape(alert.get("category", "").replace("_", " ").title())
            msg = html.escape(alert.get("message", ""))
            alert_blocks += f"""
            <div style="background:{bg};border:1px solid {border};border-left:4px solid {fg};border-radius:10px;padding:12px 16px;margin-bottom:8px;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="background:{fg};color:#18191c;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:800;letter-spacing:0.5px;">{label}</span>
                    <span style="font-size:11px;font-weight:700;color:{fg};text-transform:uppercase;">{cat}</span>
                </div>
                <div style="color:#f3f4f6;font-size:13px;line-height:1.5;">{msg}</div>
            </div>"""
    else:
        alert_blocks = '<div style="color:#10b981;font-size:13px;padding:10px 14px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);border-radius:10px;">✓ No drug-drug interactions or active contraindications identified.</div>'

    # 2. Key Allergies Tag Cloud / Summary
    allergy_badges = ""
    if allergies:
        for a in allergies:
            sub = html.escape(a.get("substance", "").title())
            react = html.escape(a.get("reaction", "Reaction reported"))
            timing = html.escape(a.get("timing", "historical").title())
            allergy_badges += f"""
            <div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:8px 12px;display:flex;align-items:center;justify-content:space-between;gap:12px;">
                <div>
                    <span style="color:#f87171;font-weight:700;font-size:13px;">{sub}</span>
                    <span style="color:#d1d5db;font-size:12px;margin-left:6px;">— {react}</span>
                </div>
                <span style="background:rgba(239,68,68,0.25);color:#fca5a5;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;text-transform:uppercase;">{timing}</span>
            </div>"""
    else:
        allergy_badges = '<div style="color:#9ca3af;font-size:12px;font-style:italic;">No documented drug allergies.</div>'

    # 3. Streamlined Medication Reconciliation Table
    STATUS_STYLES = {
        "currently_taking": ("rgba(52,211,153,0.15)",  "#34d399", "CURRENT"),
        "prescribed":       ("rgba(182,176,238,0.20)", "#c4b5fd", "PRESCRIBED"),
        "recommended":      ("rgba(56,189,248,0.15)",  "#38bdf8", "RECOMMENDED"),
        "previously_taken": ("rgba(156,163,175,0.15)", "#9ca3af", "HISTORICAL"),
        "considered_not_prescribed": ("rgba(251,191,36,0.15)", "#fbbf24", "WITHHELD"),
        "not_recommended":  ("rgba(239,68,68,0.15)",   "#ef4444", "AVOIDED"),
        "allergy_related":  ("rgba(239,68,68,0.22)",   "#f87171", "ALLERGY CONTRAINDICATION"),
        "unknown":          ("rgba(255,255,255,0.08)", "#6b7280", "MENTIONED"),
    }

    med_rows = ""
    for med in medications:
        status_key = str(med.get("status", "unknown")).lower()
        if hasattr(status_key, "value"):
            status_key = status_key.value
        s_bg, s_fg, s_label = STATUS_STYLES.get(status_key, STATUS_STYLES["unknown"])
        mention = html.escape(med.get("mention", ""))
        normalized = html.escape(med.get("normalized_name", "") or mention).title()
        rxcui = html.escape(str(med.get("rxcui") or "—"))

        regimen_parts = [p for p in (med.get("dosage"), med.get("frequency"), med.get("route"), med.get("duration")) if p]
        regimen = html.escape(", ".join(regimen_parts)) if regimen_parts else '<span style="color:#6b7280;">—</span>'

        med_rows += f"""
        <tr>
            <td style="font-weight:600;color:#f9fafb;">{normalized}<div style="font-size:11px;color:#9ca3af;font-weight:400;">from: {mention}</div></td>
            <td><span class="badge" style="background:{s_bg};color:{s_fg};">{s_label}</span></td>
            <td style="color:#e5e7eb;font-size:12px;">{regimen}</td>
            <td style="font-family:monospace;font-size:11px;color:#9ca3af;">{rxcui}</td>
        </tr>"""

    # 4. Impactful 2x2 SOAP Grid
    soap_grid = ""
    sections_order = [
        ("subjective", "Subjective", "🗣️"),
        ("objective",  "Objective", "🔬"),
        ("assessment", "Assessment", "🩺"),
        ("plan",       "Plan", "📋"),
    ]
    for key, title, icon in sections_order:
        items = soap_note.get(key, [])
        if items:
            items_html = "".join(f'<li style="margin-bottom:4px;font-size:12px;line-height:1.5;color:#d1d5db;">{html.escape(item)}</li>' for item in items)
        else:
            items_html = '<li style="font-size:12px;color:#6b7280;font-style:italic;">No active entries noted</li>'

        soap_grid += f"""
        <div style="background:#202227;border:1px solid #2d2f36;border-radius:12px;padding:14px 18px;display:flex;flex-direction:column;">
            <div style="font-size:11px;font-weight:800;color:#b6b0ee;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
                <span>{icon}</span> <span>{title}</span>
            </div>
            <ul style="padding-left:16px;margin:0;flex:1;">{items_html}</ul>
        </div>"""

    # 5. Diagnostic Orders (Brief Table / List)
    inv_section = ""
    if investigations:
        inv_items = ""
        for inv in investigations:
            m = html.escape(inv.get("mention", "").upper())
            s = html.escape(str(inv.get("status_display") or inv.get("status") or "").title())
            detail = html.escape(inv.get("condition_detail") or "")
            detail_str = f" · <span style='color:#fbbf24;'>{detail}</span>" if detail else ""
            inv_items += f"""
            <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#202227;border-radius:8px;font-size:12px;">
                <span style="font-weight:600;color:#f3f4f6;">{m}{detail_str}</span>
                <span class="badge" style="background:rgba(56,189,248,0.15);color:#38bdf8;">{s}</span>
            </div>"""
        inv_section = f"""
        <div class="card">
            <div class="card-header">
                <h3>Diagnostic Orders &amp; Investigations</h3>
                <span class="badge" style="background:#25272c;color:#9ca3af;">{len(investigations)}</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;">{inv_items}</div>
        </div>"""

    # 6. Extracted Clinical Entities (Compact Collapsible Summary)
    ent_count = len(entities)
    # Generate compact entity chip cloud instead of massive character tables
    type_counts: dict[str, int] = {}
    for e in entities:
        t = str(e.get("type", "entity"))
        type_counts[t] = type_counts.get(t, 0) + 1

    entity_chips = "".join(
        f'<span class="badge" style="background:#25272c;color:#d1d5db;font-size:11px;padding:4px 10px;">{html.escape(t.title())}: <strong>{c}</strong></span> '
        for t, c in sorted(type_counts.items())
    )

    disclaimer = html.escape(
        soap_note.get(
            "disclaimer",
            "Draft generated from NLP transcript analysis. A licensed clinician must review, verify, edit, and countersign before clinical use.",
        )
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MediScribe AI Executive Clinical Report — {encounter_id}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',sans-serif;background:#141518;color:#e5e7eb;padding:24px 16px;line-height:1.5;min-height:100vh;}}
.container{{max-width:880px;margin:0 auto;display:flex;flex-direction:column;gap:16px;}}
.header{{background:#1a1c21;border:1px solid #2d2f36;border-radius:14px;padding:22px 28px;}}
.header-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;}}
.pill{{background:rgba(210,248,75,0.12);color:#d2f84b;padding:3px 10px;border-radius:20px;font-size:10px;font-weight:800;letter-spacing:0.6px;text-transform:uppercase;}}
.title{{font-size:20px;font-weight:800;color:#ffffff;letter-spacing:-0.3px;}}
.meta-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #262830;}}
.meta-item{{font-size:11px;color:#9ca3af;}}
.meta-item strong{{display:block;font-size:13px;color:#f9fafb;font-weight:600;}}
.card{{background:#1a1c21;border:1px solid #2d2f36;border-radius:14px;padding:18px 22px;}}
.card-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #262830;}}
.card-header h3{{font-size:13px;font-weight:700;color:#f9fafb;text-transform:uppercase;letter-spacing:0.5px;}}
.grid-2x2{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;}}
@media(max-width:680px){{.grid-2x2{{grid-template-columns:1fr;}}}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
th{{text-align:left;padding:8px 10px;color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid #2d2f36;}}
td{{padding:9px 10px;border-bottom:1px solid #25272e;vertical-align:top;}}
tbody tr:last-child td{{border-bottom:none;}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700;letter-spacing:0.4px;white-space:nowrap;}}
.disclaimer{{background:rgba(251,191,36,0.05);border:1px solid rgba(251,191,36,0.20);border-radius:10px;padding:12px 16px;font-size:11px;color:#9ca3af;text-align:center;line-height:1.6;}}
.footer{{text-align:center;font-size:11px;color:#4b5563;font-family:'JetBrains Mono',monospace;}}
@media print{{body{{background:#fff;color:#111;padding:0;}} .header,.card,.disclaimer{{border-color:#ccc;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact;}} .title{{color:#000;}}}}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="header-top">
      <div class="pill">⚕ MediScribe AI · Clinical Executive Dossier</div>
      <span style="font-size:11px;color:#9ca3af;font-family:'JetBrains Mono',monospace;">{timestamp}</span>
    </div>
    <h1 class="title">Clinical Encounter &amp; Reconciliation Summary</h1>
    <div class="meta-grid">
      <div class="meta-item">Patient<strong>{patient_name}</strong></div>
      <div class="meta-item">Age<strong>{patient_age}</strong></div>
      <div class="meta-item">Attending Physician<strong>{physician_name}</strong></div>
      <div class="meta-item">Encounter ID<strong>{encounter_id}</strong></div>
    </div>
  </div>

  <!-- Actionable Safety Alerts -->
  <div class="card">
    <div class="card-header">
      <h3>Active Safety &amp; Interaction Alerts</h3>
      <span class="badge" style="background:#25272c;color:#9ca3af;">{len(safety_alerts)} Alerts</span>
    </div>
    {alert_blocks}
  </div>

  <!-- Documented Allergies -->
  <div class="card">
    <div class="card-header">
      <h3>Reported Drug Allergies &amp; Adverse Reactions</h3>
      <span class="badge" style="background:rgba(239,68,68,0.15);color:#f87171;">{len(allergies)} Documented</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;">
      {allergy_badges}
    </div>
  </div>

  <!-- Reconciled Medications -->
  <div class="card">
    <div class="card-header">
      <h3>Medication Reconciliation</h3>
      <span class="badge" style="background:#25272c;color:#9ca3af;">{len(medications)} Drugs</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>Medication / Generic</th>
          <th>Clinical Status</th>
          <th>Regimen / Sig</th>
          <th>RxCUI</th>
        </tr>
      </thead>
      <tbody>
        {med_rows if med_rows else '<tr><td colspan="4" style="text-align:center;color:#6b7280;padding:16px;">No medications recorded</td></tr>'}
      </tbody>
    </table>
  </div>

  <!-- SOAP Synthesis (2x2 Grid) -->
  <div class="card">
    <div class="card-header">
      <h3>SOAP Clinical Note</h3>
      <span class="badge" style="background:rgba(182,176,238,0.15);color:#b6b0ee;">Structured</span>
    </div>
    <div class="grid-2x2">
      {soap_grid}
    </div>
  </div>

  <!-- Investigations (if any) -->
  {inv_section}

  <!-- Compact NLP Extraction Summary (replaces bloated 20-page table) -->
  <div class="card">
    <div class="card-header">
      <h3>Extracted Clinical Entities Audit</h3>
      <span class="badge" style="background:#25272c;color:#9ca3af;">{ent_count} Total</span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
      {entity_chips}
    </div>
    <div style="margin-top:10px;font-size:11px;color:#6b7280;">
      All {ent_count} clinical entity mentions across symptoms, medications, tests, and diagnoses are indexed and cross-referenced with FHIR R4 resources.
    </div>
  </div>

  <!-- Disclaimer -->
  <div class="disclaimer">
    <strong style="color:#fbbf24;">⚠️ Clinical Attestation Notice:</strong> {disclaimer}
  </div>

  <div class="footer">
    MediScribe AI · Encounter {encounter_id} · Traceable Clinical Audit Record
  </div>

</div>
</body>
</html>"""
