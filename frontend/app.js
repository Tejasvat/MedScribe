/* ======================================================
   MediScribe AI — Frontend Application Logic v2
   Multi-page Results workspace, confidence-scored
   clickable transcript, clinical NER review tools.
   Backend contract unchanged:
     POST /v1/analyze-text  (FormData: text, encounter_id?, patient_id?)
     POST /v1/analyze-file  (FormData: file, encounter_id?, patient_id?)
     POST /v1/report        (JSON body: full result) -> returns HTML
     GET  /v1/sample-pdf
   Result shape unchanged:
     { encounter_id, entities[], medications[], safety_alerts[], turns[], soap_note{}, fhir_bundle{} }
   ====================================================== */

(() => {
    'use strict';

    // ───── Application State ─────
    let currentResult = null;
    let selectedFile = null;
    let activeFilter = 'all';
    let highlightLowConf = false;
    let reviewStatus = {}; // entity_id -> 'accepted' | 'flagged' | 'rejected'

    const API_BASE = ''; // Same origin

    const ENTITY_COLORS = {
        symptom:        { fg: '#c2410c', bg: '#fff1e8' },
        drug:           { fg: '#1d4ed8', bg: '#eaf1ff' },
        dosage:         { fg: '#7e22ce', bg: '#f6edfe' },
        frequency:      { fg: '#15803d', bg: '#e9f8ee' },
        duration:       { fg: '#be123c', bg: '#fdeef1' },
        test:           { fg: '#0e7490', bg: '#e6f7fa' },
        adverse_event:  { fg: '#9f1239', bg: '#fdecef' },
    };

    // ───── Presets Data ─────
    const PRESETS = {
        cardiology: {
            title: "Cardiology & Anticoagulant Risk",
            text: `Patient: Doctor, I have had high fever, severe cough, and chest tightness for three days. I took Paracetamol 500 mg twice daily, but it caused severe nausea and vomiting.

Doctor: I understand. Let us discontinue the paracetamol for now. Have you had any chills or shortness of breath?

Patient: Yes, breathlessness especially when climbing stairs. Also, I am currently taking warfarin 5 mg once daily for atrial fibrillation.

Doctor: Noted. Because of your cardiac history, we cannot combine ibuprofen with warfarin due to severe bleeding risk. I will order a complete blood count, troponin test, and an electrocardiogram (ECG). I will also prescribe amoxicillin 500 mg three times daily for 7 days to cover bacterial pneumonia.

Patient: I also take lisinopril 10 mg daily for hypertension. Should I continue it?

Doctor: Yes, continue lisinopril 10 mg once daily. Let us also schedule a chest X-ray this afternoon. If you experience dizziness or worsening fatigue, call our emergency line immediately.`
        },
        code_mixed: {
            title: "English–Tamil Code-Mixed (Feature A)",
            text: `Patient: Doctor, enakku severe fever and dry cough irukku since Monday. I took Paracetamol 650 mg twice daily after food, but headache innum korayala.

Doctor: Saringa. Any chest pain or breathlessness irukka?

Patient: Konjam tiredness and dizziness irukku doctor. Also stomach pain after taking tablet.

Doctor: Alright, Paracetamol stop pannunga. I will prescribe Azithromycin 500 mg once daily for 5 days. Also order complete blood count and blood glucose test to rule out infection. Take Pantoprazole 40 mg before breakfast for gastric protection.

Patient: Thank you doctor, I will take the blood test today itself.`
        },
        polypharmacy: {
            title: "Polypharmacy & Renal Interaction",
            text: `Doctor: Good morning Mr. Sharma, let us review your current medications for your type 2 diabetes and hypertension.

Patient: Good morning doctor. I am taking metformin 1000 mg twice daily and lisinopril 20 mg once daily. Lately I have had swollen ankles and knee joint pain for two weeks.

Doctor: For the joint swelling, I notice someone suggested ibuprofen 400 mg. We must avoid combining ibuprofen with lisinopril as that severely impairs renal perfusion. I also want to check your potassium and serum creatinine.

Patient: My previous doctor also mentioned adding spironolactone 25 mg for fluid retention.

Doctor: Spironolactone combined with lisinopril carries a critical risk of life-threatening hyperkalemia. We will defer spironolactone until after the basic metabolic panel results are in. Continue metformin and lisinopril, order BMP and HbA1c, and use paracetamol for mild analgesia.`
        },
        outpatient: {
            title: "General Practice Outpatient Visit",
            text: `Patient: Hello doctor, I have a sore throat, runny nose, and moderate fever that started four days ago. I have also noticed difficulty swallowing and severe fatigue.

Doctor: Let me examine your pharynx. Tonsils appear erythematous. Have you taken any over-the-counter medicine?

Patient: I took ibuprofen 200 mg yesterday, but it did not help much. I am allergic to penicillin and amoxicillin — they give me hives and skin rash.

Doctor: Thank you for alerting me to the penicillin allergy. I will document the allergic reaction. Instead of beta-lactams, I will prescribe azithromycin 250 mg once daily for 5 days. Let us also do a rapid strep test and throat culture. Drink plenty of warm fluids.`
        }
    };

    // ───── DOM Helpers ─────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ───── Navbar Scroll Effect ─────
    const navbar = $('#navbar');
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 40);
    }, { passive: true });

    /* ======================================================
       SPA ROUTER
       Pages: Home, Analyze (input), Results (multi-subpage)
       Result subpages: overview, transcript, entities,
       medications, safety, soap, fhir — all live under
       #/results[/subpage] and share one sidebar.
       ====================================================== */
    const RESULT_SUBPAGES = ['overview', 'transcript', 'entities', 'medications', 'safety', 'soap', 'fhir'];

    function parseRoute(hash) {
        let route = hash || window.location.hash || '#/';
        if (!route.startsWith('#/')) route = '#/';
        const parts = route.replace('#/', '').split('/').filter(Boolean);

        if (parts.length === 0) return { page: 'home' };
        if (parts[0] === 'analyze') return { page: 'analyze' };
        if (parts[0] === 'results') {
            const sub = RESULT_SUBPAGES.includes(parts[1]) ? parts[1] : 'overview';
            return { page: 'results', sub };
        }
        return { page: 'home' };
    }

    function navigateTo(hash) {
        const { page, sub } = parseRoute(hash);

        // Guard: no result yet but trying to view a results subpage
        if (page === 'results' && !currentResult) {
            $$('.page').forEach(p => p.classList.remove('active'));
            $('#page-results').classList.add('active');
            $('#results-guard').style.display = '';
            $$('.results-subpage').forEach(sp => sp.classList.remove('active'));
            updateNavActiveStates('results', null);
            window.scrollTo({ top: 0, behavior: 'smooth' });
            return;
        }

        // Toggle top-level pages
        $$('.page').forEach(p => p.classList.remove('active'));
        const pageEl = $(`#page-${page}`);
        if (pageEl) pageEl.classList.add('active');

        if (page === 'results') {
            $('#results-guard').style.display = 'none';
            $$('.results-subpage').forEach(sp => sp.classList.remove('active'));
            const subEl = $(`#sub-${sub}`);
            if (subEl) subEl.classList.add('active');
        }

        updateNavActiveStates(page, page === 'results' ? sub : null);

        // Close mobile menu
        const navLinks = $('#nav-links');
        if (navLinks) navLinks.classList.remove('mobile-open');

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function updateNavActiveStates(page, sub) {
        $$('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.routeGroup === page);
        });
        $$('.results-nav-link').forEach(link => {
            link.classList.toggle('active', sub && link.dataset.rnav === sub);
        });
    }

    window.addEventListener('hashchange', () => navigateTo(window.location.hash));

    document.addEventListener('click', (e) => {
        const link = e.target.closest('a[data-link], a[href^="#/"]');
        if (link) {
            const href = link.getAttribute('href');
            if (href && href.startsWith('#/') && window.location.hash === href) {
                navigateTo(href);
            }
        }
    });

    const mobileToggle = $('#nav-mobile-toggle');
    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            const navLinks = $('#nav-links');
            if (navLinks) navLinks.classList.toggle('mobile-open');
        });
    }

    navigateTo(window.location.hash || '#/');

    // ───── Presets Selection ─────
    const textarea = $('#clinical-text');
    const charCount = $('#char-count');

    function updateCharCount() {
        const len = textarea.value.length;
        charCount.textContent = `${len.toLocaleString()} character${len !== 1 ? 's' : ''}`;
    }
    textarea.addEventListener('input', updateCharCount);

    function loadPreset(presetKey) {
        const preset = PRESETS[presetKey];
        if (!preset) return;
        textarea.value = preset.text;
        updateCharCount();
        $$('.preset-chip').forEach(c => c.classList.remove('active'));
        const activeChip = $(`.preset-chip[data-preset="${presetKey}"]`);
        if (activeChip) activeChip.classList.add('active');
    }

    $$('.preset-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            loadPreset(chip.dataset.preset);
            $('#tab-text').click();
            textarea.focus();
        });
    });

    loadPreset('cardiology');

    $('#load-example').addEventListener('click', () => loadPreset('cardiology'));
    $('#clear-text').addEventListener('click', () => {
        textarea.value = '';
        updateCharCount();
        textarea.focus();
    });

    // ───── Input Tabs ─────
    $$('.input-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            $$('.input-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            $$('.tab-content').forEach(tc => tc.classList.remove('active'));
            $(`#content-${tab.dataset.tab}`).classList.add('active');
        });
    });

    // ───── File Upload ─────
    const uploadZone = $('#upload-zone');
    const fileInput = $('#file-input');
    const fileInfo = $('#file-info');

    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFile(files[0]);
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });

    function handleFile(file) {
        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) { showError('File too large. Maximum size is 10 MB.'); return; }
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['pdf', 'txt', 'text', 'csv', 'md'].includes(ext)) {
            showError('Unsupported file type. Please upload PDF, TXT, CSV, or MD.');
            return;
        }
        selectedFile = file;
        uploadZone.style.display = 'none';
        fileInfo.style.display = 'block';
        $('#file-name').textContent = file.name;
        $('#file-size').textContent = formatBytes(file.size);
    }

    $('#file-remove').addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        uploadZone.style.display = '';
        fileInfo.style.display = 'none';
    });

    const btnTestSamplePdf = $('#btn-test-sample-pdf');
    if (btnTestSamplePdf) {
        btnTestSamplePdf.addEventListener('click', async () => {
            try {
                btnTestSamplePdf.textContent = '⏳ Loading Sample PDF...';
                const response = await fetch(`${API_BASE}/v1/sample-pdf`);
                if (!response.ok) throw new Error('Could not fetch sample PDF');
                const blob = await response.blob();
                const sampleFile = new File([blob], 'sample_clinical_record.pdf', { type: 'application/pdf' });
                handleFile(sampleFile);
                btnTestSamplePdf.textContent = '⚡ Analyze Sample PDF';
                runAnalysis();
            } catch (err) {
                btnTestSamplePdf.textContent = '⚡ Analyze Sample PDF';
                showError('Failed to load sample PDF: ' + err.message);
            }
        });
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // ───── Analyze Execution ─────
    $('#btn-analyze').addEventListener('click', runAnalysis);
    $('#btn-retry').addEventListener('click', () => {
        $('#results-error').style.display = 'none';
        $('#results-loading').style.display = 'none';
        resetButton();
    });

    async function runAnalysis() {
        const activeTab = $('.input-tab.active').dataset.tab;
        const encounterId = $('#encounter-id').value.trim();
        const patientId = $('#patient-id').value.trim();

        if (activeTab === 'text') {
            if (!textarea.value.trim()) { showError('Please enter or paste clinical dialogue.'); return; }
        } else if (!selectedFile) {
            showError('Please upload a PDF or text file first.');
            return;
        }

        showLoading();
        animateLoadingSteps();

        try {
            let result;
            const formData = new FormData();
            let endpoint;
            if (activeTab === 'text') {
                formData.append('text', textarea.value.trim());
                endpoint = '/v1/analyze-text';
            } else {
                formData.append('file', selectedFile);
                endpoint = '/v1/analyze-file';
            }
            if (encounterId) formData.append('encounter_id', encounterId);
            if (patientId) formData.append('patient_id', patientId);

            const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Server error' }));
                throw new Error(err.detail || `Server error: ${res.status}`);
            }
            result = await res.json();

            currentResult = result;
            reviewStatus = {};
            activeFilter = 'all';
            renderResults(result);
            resetButton();
            $('#results-loading').style.display = 'none';
            window.location.hash = '#/results';
            navigateTo('#/results');
        } catch (err) {
            showError(err.message || 'An unexpected error occurred during analysis.');
        }
    }

    function showLoading() {
        $('#results-error').style.display = 'none';
        const btn = $('#btn-analyze');
        btn.querySelector('.btn-text').textContent = 'Running Pipeline...';
        btn.querySelector('.btn-loader').style.display = '';
        btn.querySelector('.btn-icon').style.display = 'none';
        btn.disabled = true;

        $('#results-loading').style.display = '';
        $$('.loading-step').forEach(s => s.classList.remove('active', 'done'));
        $('.loading-step[data-stage="parse"]').classList.add('active');
    }

    function animateLoadingSteps() {
        const stages = ['parse', 'segment', 'ner', 'safety', 'report'];
        stages.forEach((stage, i) => {
            setTimeout(() => {
                const step = $(`.loading-step[data-stage="${stage}"]`);
                if (step) {
                    if (i > 0) {
                        const prevStep = $(`.loading-step[data-stage="${stages[i - 1]}"]`);
                        if (prevStep) { prevStep.classList.remove('active'); prevStep.classList.add('done'); }
                    }
                    step.classList.add('active');
                }
            }, i * 350);
        });
    }

    function resetButton() {
        const btn = $('#btn-analyze');
        btn.querySelector('.btn-text').textContent = 'Run NER Pipeline';
        btn.querySelector('.btn-loader').style.display = 'none';
        btn.querySelector('.btn-icon').style.display = '';
        btn.disabled = false;
    }

    function showError(message) {
        $('#results-loading').style.display = 'none';
        resetButton();
        $('#results-error').style.display = '';
        $('#error-message').textContent = message;
    }

    /* ======================================================
       MAIN RESULTS RENDERING — fills every /results/* subpage
       ====================================================== */
    function renderResults(data) {
        const entities = data.entities || [];
        const meds = data.medications || [];
        const alerts = data.safety_alerts || [];
        const turns = data.turns || [];

        // Sidebar summary
        $('#rs-encounter-id').textContent = data.encounter_id || 'N/A';
        $('#rs-stat-entities').textContent = entities.length;
        $('#rs-stat-turns').textContent = turns.length;
        $('#rs-stat-alerts').textContent = alerts.length;
        $('#rnav-count-entities').textContent = entities.length;
        $('#rnav-count-medications').textContent = meds.length;
        $('#rnav-count-safety').textContent = alerts.length;
        const safetyCountEl = $('#rnav-count-safety');
        safetyCountEl.style.display = alerts.length > 0 ? '' : 'none';

        renderOverview(data, entities, meds, alerts, turns);
        renderClickableTranscript(turns, entities, meds);
        renderEntities(entities);
        renderMedications(meds);
        renderSafetyAlerts(alerts);
        renderSoapNote(data.soap_note || {});
        renderFhir(data.fhir_bundle || {});
    }

    // ───── Overview Subpage ─────
    function renderOverview(data, entities, meds, alerts, turns) {
        const critCount = alerts.filter(a => ['critical', 'high'].includes(a.severity)).length;

        $('#overview-stats-grid').innerHTML = `
            <div class="ov-stat-card">
                <div class="ov-stat-top">
                    <span class="ov-stat-label">Entities Extracted</span>
                    <div class="ov-stat-icon" style="background:var(--teal-light);color:var(--teal-dim);"><svg viewBox="0 0 20 20" fill="currentColor"><path d="M3 3a1 1 0 000 2v8a2 2 0 002 2h10a2 2 0 002-2V5a1 1 0 100-2H3z"/></svg></div>
                </div>
                <div class="ov-stat-num">${entities.length}</div>
            </div>
            <div class="ov-stat-card">
                <div class="ov-stat-top">
                    <span class="ov-stat-label">Dialogue Turns</span>
                    <div class="ov-stat-icon" style="background:var(--blue-light);color:var(--blue);"><svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a9.06 9.06 0 01-2.347-.306c-.584.296-1.925.864-4.181 1.234-.2.032-.352-.176-.273-.362.354-.836.674-1.95.77-2.966C2.249 13.37 2 11.76 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7z" clip-rule="evenodd"/></svg></div>
                </div>
                <div class="ov-stat-num">${turns.length}</div>
            </div>
            <div class="ov-stat-card">
                <div class="ov-stat-top">
                    <span class="ov-stat-label">Medications</span>
                    <div class="ov-stat-icon" style="background:var(--purple)1a;color:var(--purple);background:#f6edfe;"><svg viewBox="0 0 20 20" fill="currentColor"><path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/><path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5z" clip-rule="evenodd"/></svg></div>
                </div>
                <div class="ov-stat-num">${meds.length}</div>
            </div>
            <div class="ov-stat-card">
                <div class="ov-stat-top">
                    <span class="ov-stat-label">Safety Alerts</span>
                    <div class="ov-stat-icon" style="background:${alerts.length ? 'var(--red-light)' : 'var(--teal-light)'};color:${alerts.length ? 'var(--red)' : 'var(--teal-dim)'};"><svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l6.517 11.59c.75 1.334-.213 2.98-1.742 2.98H3.48c-1.53 0-2.493-1.646-1.743-2.98l6.52-11.59z" clip-rule="evenodd"/></svg></div>
                </div>
                <div class="ov-stat-num" style="color:${alerts.length ? 'var(--red)' : 'var(--ink)'}">${alerts.length}</div>
            </div>
        `;

        // Entity type breakdown
        const typeCounts = {};
        entities.forEach(e => { typeCounts[e.type] = (typeCounts[e.type] || 0) + 1; });
        const maxCount = Math.max(1, ...Object.values(typeCounts));
        const breakdownEl = $('#overview-entity-breakdown');
        const typeKeys = Object.keys(typeCounts);
        if (typeKeys.length === 0) {
            breakdownEl.innerHTML = '<div class="ov-empty-mini">No entities extracted for this encounter.</div>';
        } else {
            breakdownEl.innerHTML = typeKeys.sort((a, b) => typeCounts[b] - typeCounts[a]).map(type => {
                const c = ENTITY_COLORS[type] || { fg: '#44586a', bg: '#eef2f5' };
                const pct = (typeCounts[type] / maxCount) * 100;
                return `
                    <div class="ov-type-row">
                        <span class="ov-type-dot" style="background:${c.fg}"></span>
                        <span class="ov-type-name">${escapeHtml(type.replace('_', ' '))}</span>
                        <div class="ov-type-bar-track"><div class="ov-type-bar-fill" style="width:${pct}%;background:${c.fg}"></div></div>
                        <span class="ov-type-count">${typeCounts[type]}</span>
                    </div>`;
            }).join('');
        }

        // Safety preview
        const safetyEl = $('#overview-safety-preview');
        if (alerts.length === 0) {
            safetyEl.innerHTML = '<div class="ov-empty-mini">✅ No interactions or conflicts detected.</div>';
        } else {
            safetyEl.innerHTML = alerts.slice(0, 4).map(a => `
                <div class="ov-alert-mini">
                    <span class="ov-alert-sev severity-badge severity-${a.severity}">${escapeHtml((a.severity || '').toUpperCase())}</span>
                    <span class="ov-alert-text">${escapeHtml(a.message)}</span>
                </div>`).join('') + (alerts.length > 4 ? `<a href="#/results/safety" data-link style="font-size:12.5px;font-weight:600;color:var(--teal-dim);display:inline-block;margin-top:10px;">View all ${alerts.length} alerts →</a>` : '');
        }
    }

    // ───── Clickable Confidence-Scored Transcript ─────
    function renderClickableTranscript(turns, entities, meds) {
        const container = $('#rtab-transcript');
        if (!turns || turns.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--ink-muted);padding:32px;">No transcript turns available.</p>';
            return;
        }

        const entitiesByTurn = {};
        const entityMap = {};
        entities.forEach(ent => {
            entityMap[ent.entity_id] = ent;
            const tId = ent.provenance?.turn_id || 'unknown';
            if (!entitiesByTurn[tId]) entitiesByTurn[tId] = [];
            entitiesByTurn[tId].push(ent);
        });

        const typeCounts = { all: entities.length };
        entities.forEach(e => { typeCounts[e.type] = (typeCounts[e.type] || 0) + 1; });

        const toolbarHtml = `
            <div class="transcript-toolbar">
                <div class="transcript-filters">
                    <button class="filter-chip ${activeFilter === 'all' ? 'active' : ''}" data-filter="all">All Spans (${typeCounts.all || 0})</button>
                    <button class="filter-chip ${activeFilter === 'symptom' ? 'active' : ''}" data-filter="symptom">Symptoms (${typeCounts.symptom || 0})</button>
                    <button class="filter-chip ${activeFilter === 'drug' ? 'active' : ''}" data-filter="drug">Drugs (${typeCounts.drug || 0})</button>
                    <button class="filter-chip ${activeFilter === 'dosage' ? 'active' : ''}" data-filter="dosage">Dosage (${typeCounts.dosage || 0})</button>
                    <button class="filter-chip ${activeFilter === 'frequency' ? 'active' : ''}" data-filter="frequency">Frequency (${typeCounts.frequency || 0})</button>
                    <button class="filter-chip ${activeFilter === 'test' ? 'active' : ''}" data-filter="test">Tests (${typeCounts.test || 0})</button>
                    <button class="filter-chip ${activeFilter === 'adverse_event' ? 'active' : ''}" data-filter="adverse_event">Adverse (${typeCounts.adverse_event || 0})</button>
                </div>
                <label class="transcript-toggle-wrap">
                    <input type="checkbox" id="toggle-low-conf" ${highlightLowConf ? 'checked' : ''}>
                    <span>Flag Low-Confidence (&lt;80%)</span>
                </label>
            </div>
        `;

        const turnsHtml = turns.map((turn, tIdx) => {
            const turnEntities = entitiesByTurn[turn.turn_id] || [];
            const speaker = (turn.speaker || 'unknown').toLowerCase();
            const speakerLabel = speaker === 'clinician' ? '👨‍⚕️ Clinician / Doctor' : speaker === 'patient' ? '🧑 Patient' : 'Note / Turn';
            const highlightedText = highlightEntitiesInText(turn.text, turnEntities, activeFilter, highlightLowConf);

            return `
                <div class="transcript-turn-card speaker-${speaker}" id="turn-${turn.turn_id}">
                    <div class="turn-header">
                        <span class="turn-speaker-badge">${speakerLabel}</span>
                        <span class="turn-id-tag">Turn #${tIdx + 1} (${escapeHtml(turn.turn_id)})</span>
                    </div>
                    <div class="turn-text-content">${highlightedText}</div>
                </div>`;
        }).join('');

        container.innerHTML = `<div class="transcript-box">${toolbarHtml}<div class="transcript-turns-list">${turnsHtml}</div></div>`;

        container.querySelectorAll('.filter-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                activeFilter = btn.dataset.filter;
                renderClickableTranscript(turns, entities, meds);
            });
        });

        const toggle = container.querySelector('#toggle-low-conf');
        if (toggle) {
            toggle.addEventListener('change', (e) => {
                highlightLowConf = e.target.checked;
                renderClickableTranscript(turns, entities, meds);
            });
        }

        container.querySelectorAll('.entity-mark').forEach(mark => {
            mark.addEventListener('click', (e) => {
                e.stopPropagation();
                const ent = entityMap[mark.dataset.entityId];
                if (ent) showEntityPopover(ent, meds);
            });
        });
    }

    function highlightEntitiesInText(text, entities, filterType, flagLowConf) {
        if (!entities || entities.length === 0) return escapeHtml(text);
        const filtered = entities.filter(ent => filterType === 'all' || ent.type === filterType);
        if (filtered.length === 0) return escapeHtml(text);

        const matches = [];
        filtered.forEach(ent => {
            const needle = ent.text;
            if (!needle) return;
            const regex = new RegExp(`\\b${escapeRegex(needle)}\\b`, 'gi');
            let m;
            while ((m = regex.exec(text)) !== null) {
                matches.push({ start: m.index, end: m.index + m[0].length, matchedText: m[0], entity: ent });
            }
        });
        if (matches.length === 0) return escapeHtml(text);

        matches.sort((a, b) => a.start - b.start);
        const nonOverlapping = [];
        let lastEnd = 0;
        for (const m of matches) {
            if (m.start >= lastEnd) { nonOverlapping.push(m); lastEnd = m.end; }
        }

        let result = '';
        let cursor = 0;
        for (const m of nonOverlapping) {
            result += escapeHtml(text.substring(cursor, m.start));
            const conf = parseFloat(m.entity.confidence) || 0;
            const isLowConf = flagLowConf && conf < 0.80;
            const status = reviewStatus[m.entity.entity_id];
            const statusClass = status ? `status-${status}` : '';
            result += `<mark class="entity-mark type-${m.entity.type} ${isLowConf ? 'low-confidence' : ''} ${statusClass}"
                           data-entity-id="${m.entity.entity_id}"
                           title="${m.entity.type.toUpperCase()}: ${escapeHtml(m.matchedText)} (${(conf * 100).toFixed(0)}% confidence - Click to inspect)">${escapeHtml(m.matchedText)}</mark>`;
            cursor = m.end;
        }
        result += escapeHtml(text.substring(cursor));
        return result;
    }

    function escapeRegex(str) { return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

    // ───── Entity Details Popover ─────
    function showEntityPopover(entity, meds) {
        const existing = $('.entity-popover-backdrop');
        if (existing) existing.remove();

        const conf = parseFloat(entity.confidence) || 0;
        const confPercent = (conf * 100).toFixed(0);
        const confClass = conf >= 0.8 ? 'high' : conf >= 0.6 ? 'med' : 'low';
        const matchedMed = meds.find(m => m.entity_id === entity.entity_id || m.mention.toLowerCase() === entity.text.toLowerCase());

        const popover = document.createElement('div');
        popover.className = 'entity-popover-backdrop';
        popover.innerHTML = `
            <div class="entity-popover-card">
                <div class="popover-header">
                    <div class="popover-title-box">
                        <span class="entity-type-badge badge-${entity.type}">${entity.type.toUpperCase()}</span>
                        <h4>${escapeHtml(entity.text)}</h4>
                    </div>
                    <button class="popover-close-btn" id="popover-close">✕</button>
                </div>
                <div class="popover-stat-grid">
                    <div class="popover-stat-item"><span class="popover-stat-label">Category</span><span class="popover-stat-val">${entity.type.replace('_', ' ').toUpperCase()}</span></div>
                    <div class="popover-stat-item"><span class="popover-stat-label">RxNorm / Concept</span><span class="popover-stat-val">${matchedMed ? escapeHtml(matchedMed.normalized_name || 'Generic') : (entity.normalized_text || 'Exact span')}</span></div>
                    ${matchedMed && matchedMed.rxcui ? `<div class="popover-stat-item"><span class="popover-stat-label">RxCUI Code</span><span class="popover-stat-val" style="font-family:monospace;color:var(--teal-dim)">#${escapeHtml(matchedMed.rxcui)}</span></div>` : ''}
                    <div class="popover-stat-item"><span class="popover-stat-label">Provenance Turn</span><span class="popover-stat-val">Turn #${escapeHtml(entity.provenance?.turn_id || '1')}</span></div>
                </div>
                <div class="popover-meter-box">
                    <div class="popover-meter-header"><span>Extraction Confidence</span><span style="color:${conf >= 0.8 ? '#059669' : conf >= 0.6 ? '#d97706' : '#dc2626'}">${confPercent}%</span></div>
                    <div class="popover-meter-bar"><div class="popover-meter-fill ${confClass}" style="width:${confPercent}%"></div></div>
                </div>
                <div class="popover-provenance">"…${escapeHtml(entity.provenance?.source_text || entity.text)}…"</div>
                <div class="popover-review-box">
                    <span style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--ink-muted);display:block;margin-bottom:6px;">Clinician Review Decision</span>
                    <div class="popover-review-actions">
                        <button class="btn-review btn-review-accept" id="btn-accept">✓ Accept</button>
                        <button class="btn-review btn-review-flag" id="btn-flag">🚩 Flag Review</button>
                        <button class="btn-review btn-review-reject" id="btn-reject">✗ Dismiss</button>
                    </div>
                </div>
            </div>`;

        document.body.appendChild(popover);

        popover.addEventListener('click', (e) => {
            if (e.target === popover || e.target.id === 'popover-close') popover.remove();
        });
        popover.querySelector('#btn-accept').addEventListener('click', () => {
            reviewStatus[entity.entity_id] = 'accepted';
            updateEntityMarkReview(entity.entity_id, 'accepted');
            popover.remove();
        });
        popover.querySelector('#btn-flag').addEventListener('click', () => {
            reviewStatus[entity.entity_id] = 'flagged';
            updateEntityMarkReview(entity.entity_id, 'flagged');
            popover.remove();
        });
        popover.querySelector('#btn-reject').addEventListener('click', () => {
            reviewStatus[entity.entity_id] = 'rejected';
            updateEntityMarkReview(entity.entity_id, 'rejected');
            popover.remove();
        });
    }

    function updateEntityMarkReview(entityId, status) {
        $$(`.entity-mark[data-entity-id="${entityId}"]`).forEach(m => {
            m.classList.remove('status-accepted', 'status-flagged', 'status-rejected');
            m.classList.add(`status-${status}`);
            if (status === 'accepted') m.style.outline = '2px solid #10b981';
            else if (status === 'flagged') m.style.outline = '2px solid #f59e0b';
            else if (status === 'rejected') m.style.textDecoration = 'line-through';
        });
    }

    // ───── Entities Table ─────
    function renderEntities(entities) {
        if (entities.length === 0) {
            $('#rtab-entities').innerHTML = '<p style="text-align:center;color:var(--ink-muted);padding:32px;">No entities extracted.</p>';
            return;
        }
        let rows = entities.map(ent => {
            const conf = parseFloat(ent.confidence) || 0;
            const confClass = conf >= 0.8 ? 'high' : conf >= 0.5 ? 'medium' : 'low';
            const source = ent.provenance ? (ent.provenance.source_text || '') : '';
            return `
            <tr class="entity-row-clickable" data-entity-id="${ent.entity_id}" title="Click to view in Clickable Transcript">
                <td><span class="entity-type-badge badge-${ent.type}">${escapeHtml(ent.type.toUpperCase())}</span></td>
                <td><strong>${escapeHtml(ent.text)}</strong></td>
                <td>
                    <div class="confidence-cell">
                        <div class="conf-mini-bar"><div class="conf-mini-fill ${confClass}" style="width:${(conf * 100).toFixed(0)}%"></div></div>
                        <span class="conf-text">${(conf * 100).toFixed(0)}%</span>
                    </div>
                </td>
                <td><span class="source-snippet" title="${escapeHtml(source)}">${escapeHtml(source.substring(0, 60))}${source.length > 60 ? '…' : ''}</span></td>
                <td><button class="btn-jump-transcript">View In Transcript →</button></td>
            </tr>`;
        }).join('');

        $('#rtab-entities').innerHTML = `
            <table class="entity-table">
                <thead><tr><th>Type</th><th>Entity</th><th>Confidence</th><th>Source Sentence</th><th>Action</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>`;

        $('#rtab-entities').querySelectorAll('.entity-row-clickable').forEach(row => {
            row.addEventListener('click', () => jumpToEntityInTranscript(row.dataset.entityId));
        });
    }

    function jumpToEntityInTranscript(entityId) {
        window.location.hash = '#/results/transcript';
        navigateTo('#/results/transcript');
        setTimeout(() => {
            const mark = $(`.entity-mark[data-entity-id="${entityId}"]`);
            if (mark) {
                mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
                mark.classList.add('highlight-active');
                setTimeout(() => mark.classList.remove('highlight-active'), 2500);
            }
        }, 200);
    }

    // ───── Medications ─────
    function renderMedications(meds) {
        if (meds.length === 0) {
            $('#rtab-medications').innerHTML = '<p style="text-align:center;color:var(--ink-muted);padding:32px;">No medications found.</p>';
            return;
        }
        let rows = meds.map(med => `
            <tr>
                <td><strong>${escapeHtml(med.mention)}</strong></td>
                <td>${escapeHtml(med.normalized_name || 'N/A')}</td>
                <td>${med.rxcui ? `<span class="rxcui-badge">RxCUI #${escapeHtml(med.rxcui)}</span>` : '<span style="color:var(--ink-muted)">—</span>'}</td>
                <td><span style="font-weight:600;color:${parseFloat(med.normalization_confidence) >= 0.9 ? 'var(--teal-dim)' : 'var(--amber)'}">${(parseFloat(med.normalization_confidence) * 100).toFixed(0)}%</span></td>
            </tr>`).join('');

        $('#rtab-medications').innerHTML = `
            <table class="med-table">
                <thead><tr><th>Extracted Mention</th><th>Normalized Generic (RxNorm)</th><th>RxCUI Concept</th><th>Confidence</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    // ───── Safety Alerts ─────
    function renderSafetyAlerts(alerts) {
        if (alerts.length === 0) {
            $('#rtab-safety').innerHTML = `
                <div class="safety-empty-state">
                    <div class="se-icon">✅</div>
                    <h4>No Safety Alerts Detected</h4>
                    <p>No drug–drug interactions or duplicate therapies flagged by the DDInter / RxNorm safety engine.</p>
                </div>`;
            return;
        }
        $('#rtab-safety').innerHTML = `<div class="safety-alert-list">${alerts.map(alert => `
            <div class="alert-card-result severity-${alert.severity}">
                <div class="alert-result-header">
                    <span class="severity-badge severity-${alert.severity}">${escapeHtml(alert.severity.toUpperCase())}</span>
                    <span class="category-label">${escapeHtml((alert.category || '').replace(/_/g, ' '))}</span>
                </div>
                <p>${escapeHtml(alert.message)}</p>
            </div>`).join('')}</div>`;
    }

    // ───── SOAP Note ─────
    function renderSoapNote(soap) {
        const sections = [
            { key: 'subjective', label: 'Subjective', letter: 'S' },
            { key: 'objective', label: 'Objective', letter: 'O' },
            { key: 'assessment', label: 'Assessment', letter: 'A' },
            { key: 'plan', label: 'Plan', letter: 'P' },
        ];
        let cards = sections.map(sec => {
            const items = soap[sec.key] || [];
            const lis = items.length > 0 ? items.map(item => `<li>${escapeHtml(item)}</li>`).join('') : '<li class="soap-empty">No entries documented</li>';
            return `<div class="soap-card"><h4><span class="soap-letter">${sec.letter}</span> ${sec.label}</h4><ul>${lis}</ul></div>`;
        }).join('');

        const disclaimer = soap.disclaimer ? `<div class="soap-disclaimer">⚠️ ${escapeHtml(soap.disclaimer)}</div>` : '';
        $('#rtab-soap').innerHTML = `<div class="soap-grid">${cards}${disclaimer}</div>`;
    }

    // ───── FHIR Bundle ─────
    function renderFhir(bundle) {
        $('#rtab-fhir').innerHTML = `<pre class="fhir-json">${escapeHtml(JSON.stringify(bundle, null, 2))}</pre>`;
    }

    // ───── Sidebar Actions: Print / Download ─────
    const btnPrintReport = $('#btn-print-report');
    if (btnPrintReport) btnPrintReport.addEventListener('click', () => window.print());

    $('#btn-download-json').addEventListener('click', () => {
        if (!currentResult) return;
        downloadJSON(currentResult, `mediscribe-${currentResult.encounter_id || 'result'}.json`);
    });

    $('#btn-download-fhir').addEventListener('click', () => {
        if (!currentResult || !currentResult.fhir_bundle) return;
        downloadJSON(currentResult.fhir_bundle, `mediscribe-fhir-${currentResult.encounter_id || 'bundle'}.json`);
    });

    $('#btn-download-report').addEventListener('click', async () => {
        if (!currentResult) return;
        try {
            const res = await fetch(`${API_BASE}/v1/report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentResult),
            });
            if (!res.ok) throw new Error('Failed to generate report');
            const html = await res.text();
            const blob = new Blob([html], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `mediscribe-report-${currentResult.encounter_id || 'report'}.html`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Report generation failed:', err);
        }
    });

    function downloadJSON(data, filename) {
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ───── Utility ─────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

})();
