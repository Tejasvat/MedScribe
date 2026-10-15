"""Generate structured PDF reports from analysis results."""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any


def generate_html_report(result: dict[str, Any]) -> str:
    """Generate a downloadable HTML report styled for print/PDF."""

    encounter_id = html.escape(str(result.get("encounter_id", "N/A")))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entities = result.get("entities", [])
    medications = result.get("medications", [])
    safety_alerts = result.get("safety_alerts", [])
    soap_note = result.get("soap_note", {})

    # Build entity rows
    entity_rows = ""
    for ent in entities:
        conf = float(ent.get("confidence", 0))
        conf_class = "high" if conf >= 0.8 else "medium" if conf >= 0.5 else "low"
        entity_rows += f"""
        <tr>
            <td><span class="entity-badge entity-{html.escape(ent.get('type', 'unknown'))}">{html.escape(ent.get('type', 'N/A').upper())}</span></td>
            <td>{html.escape(ent.get('text', ''))}</td>
            <td><span class="confidence-bar {conf_class}">{conf:.0%}</span></td>
            <td class="source-text">{html.escape(ent.get('provenance', {}).get('source_text', '')[:80])}</td>
        </tr>"""

    # Build medication rows
    med_rows = ""
    for med in medications:
        med_rows += f"""
        <tr>
            <td>{html.escape(med.get('mention', ''))}</td>
            <td>{html.escape(med.get('normalized_name', 'N/A') or 'N/A')}</td>
            <td>{html.escape(med.get('rxcui', 'N/A') or 'N/A')}</td>
            <td>{float(med.get('normalization_confidence', 0)):.0%}</td>
        </tr>"""

    # Build safety alert cards
    alert_cards = ""
    for alert in safety_alerts:
        sev = alert.get("severity", "info")
        alert_cards += f"""
        <div class="alert-card alert-{html.escape(sev)}">
            <div class="alert-header">
                <span class="alert-severity">{html.escape(sev.upper())}</span>
                <span class="alert-category">{html.escape(alert.get('category', '').replace('_', ' ').title())}</span>
            </div>
            <p>{html.escape(alert.get('message', ''))}</p>
        </div>"""

    # SOAP note sections
    soap_sections = ""
    for section_key, section_label in [("subjective", "Subjective"), ("objective", "Objective"), ("assessment", "Assessment"), ("plan", "Plan")]:
        items = soap_note.get(section_key, [])
        items_html = "".join(f"<li>{html.escape(item)}</li>" for item in items) if items else "<li class='empty'>No entries</li>"
        soap_sections += f"""
        <div class="soap-section">
            <h4>{section_label}</h4>
            <ul>{items_html}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MediScribe AI — Clinical Report {encounter_id}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', sans-serif; color: #1a2332; background: #f8fafb; padding: 40px; line-height: 1.6; }}
.report-container {{ max-width: 900px; margin: 0 auto; }}
.report-header {{ background: linear-gradient(135deg, #0d2b3e 0%, #164a5f 100%); color: #fff; padding: 40px; border-radius: 16px; margin-bottom: 32px; }}
.report-header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
.report-header .subtitle {{ color: #5ee7b7; font-size: 14px; font-weight: 500; }}
.report-header .meta {{ margin-top: 16px; display: flex; gap: 32px; font-size: 13px; opacity: 0.8; }}
.section {{ background: #fff; border-radius: 12px; padding: 28px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
.section h3 {{ font-size: 18px; font-weight: 600; color: #0d2b3e; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e8ecf0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 10px 12px; background: #f0f4f7; color: #556; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #eef1f4; }}
.entity-badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }}
.entity-symptom {{ background: #fff3e0; color: #e65100; }}
.entity-drug {{ background: #e3f2fd; color: #1565c0; }}
.entity-dosage {{ background: #f3e5f5; color: #7b1fa2; }}
.entity-frequency {{ background: #e8f5e9; color: #2e7d32; }}
.entity-duration {{ background: #fce4ec; color: #c62828; }}
.entity-test {{ background: #e0f7fa; color: #00838f; }}
.entity-adverse_event {{ background: #ffebee; color: #b71c1c; }}
.confidence-bar {{ display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 600; }}
.confidence-bar.high {{ background: #e8f5e9; color: #2e7d32; }}
.confidence-bar.medium {{ background: #fff8e1; color: #f57f17; }}
.confidence-bar.low {{ background: #ffebee; color: #c62828; }}
.source-text {{ color: #889; font-size: 12px; max-width: 200px; }}
.alert-card {{ border-radius: 10px; padding: 16px; margin-bottom: 12px; }}
.alert-high {{ background: #ffebee; border-left: 4px solid #c62828; }}
.alert-moderate {{ background: #fff8e1; border-left: 4px solid #f57f17; }}
.alert-info {{ background: #e3f2fd; border-left: 4px solid #1565c0; }}
.alert-header {{ display: flex; gap: 12px; margin-bottom: 6px; }}
.alert-severity {{ font-weight: 700; font-size: 11px; text-transform: uppercase; }}
.alert-category {{ font-size: 12px; color: #667; }}
.soap-section {{ margin-bottom: 16px; }}
.soap-section h4 {{ font-size: 14px; font-weight: 600; color: #164a5f; margin-bottom: 6px; }}
.soap-section ul {{ padding-left: 20px; }}
.soap-section li {{ margin-bottom: 4px; font-size: 13px; }}
.soap-section li.empty {{ color: #aab; font-style: italic; }}
.disclaimer {{ background: #fff8e1; border: 1px solid #ffe082; border-radius: 10px; padding: 16px; font-size: 12px; color: #7a6a2f; margin-top: 24px; text-align: center; }}
@media print {{
    body {{ padding: 20px; }}
    .section {{ box-shadow: none; border: 1px solid #eee; page-break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="report-container">
    <div class="report-header">
        <div class="subtitle">· DEEP LEARNING</div>
        <h1>MediScribe AI — Clinical Report</h1>
        <div class="meta">
            <span>Encounter: {encounter_id}</span>
            <span>Generated: {timestamp}</span>
            <span>Entities: {len(entities)}</span>
            <span>Alerts: {len(safety_alerts)}</span>
        </div>
    </div>

    <div class="section">
        <h3>Extracted Clinical Entities</h3>
        <table>
            <thead><tr><th>Type</th><th>Entity</th><th>Confidence</th><th>Source</th></tr></thead>
            <tbody>{entity_rows if entity_rows else '<tr><td colspan="4" style="text-align:center;color:#aab;">No entities extracted</td></tr>'}</tbody>
        </table>
    </div>

    <div class="section">
        <h3>Normalized Medications</h3>
        <table>
            <thead><tr><th>Mention</th><th>Normalized</th><th>RxCUI</th><th>Confidence</th></tr></thead>
            <tbody>{med_rows if med_rows else '<tr><td colspan="4" style="text-align:center;color:#aab;">No medications found</td></tr>'}</tbody>
        </table>
    </div>

    <div class="section">
        <h3>Safety Alerts</h3>
        {alert_cards if alert_cards else '<p style="color:#aab;text-align:center;">No safety alerts</p>'}
    </div>

    <div class="section">
        <h3>SOAP Note (Draft)</h3>
        {soap_sections}
    </div>

    <div class="disclaimer">
        ⚠️ {html.escape(soap_note.get('disclaimer', 'Draft generated from transcript entities. A licensed clinician must review, edit, and sign before clinical use.'))}
    </div>
</div>
</body>
</html>"""
