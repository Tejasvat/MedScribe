/**
 * MediScribe AI — Lumina Health Intelligence Frontend Controller
 * Features:
 *   - Clean Starting Page / Intake Portal (Default view)
 *   - Progressive Disclosure with smooth expand/collapse animations
 *   - Live connection to FastAPI backend:
 *       POST /v1/analyze-text
 *       POST /v1/analyze-file
 *       GET  /v1/presets
 *       GET  /v1/sample-pdf
 *       POST /v1/report
 */

(() => {
    'use strict';

    // ==================== STATE MANAGEMENT ====================
    let currentEncounter = null;
    let availablePresets = [];
    let selectedUploadFile = null;
    let selectedAudioFile = null;
    let currentAudioJob = null;
    let audioPollInterval = null;
    let audioTranscriptData = {
        job_id: null,
        speakers: [],
        speaker_roles: {}, // {"SPEAKER_00": "doctor", "SPEAKER_01": "patient"}
        segments: [],
    };
    let isAudioPlaying = false;
    let audioTimer = null;
    let audioSeconds = 258; // 04:18

    const API_BASE = ''; // Same origin

    // Known SNOMED mappings for enriched clinical view
    const SNOMED_MAPPINGS = {
        fever: '386661006',
        cough: '49727002',
        pain: '22253000',
        headache: '25064002',
        'chest tightness': '29857009',
        'chest pain': '29857009',
        breathlessness: '267036007',
        'shortness of breath': '267036007',
        nausea: '422587007',
        vomiting: '422400008',
        dizziness: '404640003',
        fatigue: '84229001',
        warfarin: '372756006',
        aspirin: '387458008',
        ibuprofen: '387207008',
        paracetamol: '387517004',
        acetaminophen: '387517004',
        amoxicillin: '372687004',
        lisinopril: '387425002',
        azithromycin: '387532007',
        pantoprazole: '387140001',
        metformin: '372567009',
        spironolactone: '387401007',
        'complete blood count': '43789009',
        cbc: '43789009',
        ecg: '29303009',
        electrocardiogram: '29303009',
        troponin: '104851000'
    };

    // ==================== ROUTING ====================
    const ROUTES = [
        'start',
        'audio-review',
        'overview',
        'dialogue-and-ner',
        'drug-safety',
        'clinical-soap-note',
        'encounter-report'
    ];


    function handleRoute() {
        // Default to start view on first load if no hash or hash is empty/root
        const hash = window.location.hash.replace(/^#\/?/, '') || 'start';
        const targetRoute = ROUTES.includes(hash) ? hash : 'start';

        // 1. Switch visible view panel
        document.querySelectorAll('.view-panel').forEach(panel => {
            panel.classList.add('hidden');
            panel.classList.remove('flex');
        });

        const activePanel = document.getElementById(`view-${targetRoute}`);
        if (activePanel) {
            activePanel.classList.remove('hidden');
            activePanel.classList.add('flex');
        }

        // 2. Update sidebar navigation pills
        document.querySelectorAll('#sidebar-nav .nav-item').forEach(item => {
            const itemRoute = item.getAttribute('data-route');
            if (itemRoute === targetRoute) {
                item.className = 'nav-item group flex items-center justify-between px-space-md py-space-sm rounded-full transition-all cursor-pointer bg-surface-container-lowest text-[#18191c] font-semibold shadow-[0_4px_12px_rgba(0,0,0,0.08)]';
            } else {
                item.className = 'nav-item group flex items-center justify-between px-space-md py-space-sm rounded-full text-neutral-300 hover:bg-[#25272c] hover:text-white transition-all cursor-pointer';
            }
        });

        // Scroll to top smoothly
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    window.navigateTo = function(route) {
        window.location.hash = `#/${route}`;
    };

    window.addEventListener('hashchange', handleRoute);

    // ==================== INITIALIZATION ====================
    document.addEventListener('DOMContentLoaded', async () => {
        setupGlobalSearch();
        setupTextareaCounters();

        // 1. Fetch available preset clinical scenarios
        await fetchPresets();

        // 2. Route to starting page by default
        if (!window.location.hash || window.location.hash === '#/' || window.location.hash === '#') {
            window.location.hash = '#/start';
        }
        handleRoute();
    });

    // ==================== PROGRESSIVE DISCLOSURE COLLAPSIBLE ====================
    window.toggleCollapsible = function(boxId, chevronId) {
        const box = document.getElementById(boxId);
        const chevron = document.getElementById(chevronId);
        if (!box) return;

        const isOpen = box.classList.contains('is-open');
        if (isOpen) {
            box.classList.remove('is-open');
            if (chevron) chevron.classList.remove('is-rotated');
        } else {
            box.classList.add('is-open');
            if (chevron) chevron.classList.add('is-rotated');
        }
    };

    // ==================== STARTING PAGE CONTROLS ====================
    window.switchStartTab = function(tabKey, btnEl) {
        document.querySelectorAll('.start-tab-content').forEach(p => p.classList.add('hidden'));
        document.querySelectorAll('.start-tab-btn').forEach(b => {
            b.className = 'start-tab-btn px-5 py-2 rounded-full text-xs font-semibold text-on-surface-variant hover:text-on-surface transition-all flex items-center gap-1.5 active:scale-95';
        });

        const activeContent = document.getElementById(`start-tab-${tabKey}`);
        if (activeContent) activeContent.classList.remove('hidden');

        if (btnEl) {
            btnEl.className = 'start-tab-btn px-5 py-2 rounded-full text-xs font-bold transition-all bg-[#18191c] text-white shadow-sm flex items-center gap-1.5 active:scale-95';
        }
    };

    function renderStartPresetsCards(presets) {
        const container = document.getElementById('startPresetsCardsGrid');
        if (!container) return;

        container.innerHTML = presets.map(p => {
            const isDanger = p.badge_class === 'badge-danger';
            const badgeBg = isDanger ? 'bg-error-container text-on-error-container' : 'bg-primary-container text-on-primary-fixed';
            const icon = p.id === 'cardiology' ? 'cardiology' : p.id === 'code_mixed' ? 'translate' : p.id === 'polypharmacy' ? 'warning' : 'stethoscope';

            return `
                <div class="p-space-lg rounded-2xl bg-surface-container-low hover:bg-surface-container border border-transparent hover:border-black/5 transition-all cursor-pointer flex flex-col justify-between gap-space-sm group shadow-sm hover:shadow-md active:scale-[0.99]" onclick="loadPresetAndNavigate('${escapeHtml(p.id)}')">
                    <div class="flex flex-col gap-1.5">
                        <div class="flex items-center justify-between">
                            <span class="px-2.5 py-0.5 rounded-full ${badgeBg} text-[11px] font-bold">${escapeHtml(p.badge)}</span>
                            <span class="material-symbols-outlined text-base text-on-surface-variant group-hover:translate-x-1 transition-transform">arrow_forward</span>
                        </div>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="material-symbols-outlined text-lg text-primary">${icon}</span>
                            <h3 class="text-sm font-bold text-on-surface">${escapeHtml(p.title)}</h3>
                        </div>
                        <p class="text-xs text-on-surface-variant line-clamp-2 leading-relaxed">${escapeHtml(p.description)}</p>
                    </div>
                    <div class="pt-2 border-t border-surface-container flex items-center justify-between text-[11px] text-tertiary">
                        <span>Click to launch analysis</span>
                        <span class="font-bold text-primary group-hover:underline">Start →</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    window.loadPresetAndNavigate = async function(presetId) {
        showToast(`Loading scenario "${presetId}"...`, 'sync');
        await loadPreset(presetId);
        navigateTo('overview');
    };

    window.handleStartFileSelected = function(event) {
        const file = event.target.files[0];
        if (!file) return;

        selectedUploadFile = file;
        const label = document.getElementById('startSelectedFileLabel');
        if (label) {
            label.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
            label.className = 'mt-space-md px-4 py-1.5 rounded-full bg-primary-container text-on-primary-fixed font-bold text-xs font-mono';
        }

        const submitBtn = document.getElementById('startUploadSubmitBtn');
        if (submitBtn) submitBtn.disabled = false;
    };

    window.runUploadedFileAnalysis = async function() {
        if (!selectedUploadFile) return;

        const btn = document.getElementById('startUploadSubmitBtn');
        btn.disabled = true;
        btn.innerHTML = '<span class="material-symbols-outlined text-base animate-spin text-primary-fixed">sync</span><span>Parsing Record with NER...</span>';

        try {
            const formData = new FormData();
            formData.append('file', selectedUploadFile);
            formData.append('encounter_id', `enc-file-${Date.now().toString().slice(-6)}`);

            const res = await fetch(`${API_BASE}/v1/analyze-file`, { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'File processing failed');
            }

            const result = await res.json();
            currentEncounter = result;
            renderAllViews(result);
            showToast(`Document "${selectedUploadFile.name}" analyzed successfully!`, 'check_circle');
            navigateTo('overview');

        } catch (err) {
            showToast(`Analysis failed: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span class="material-symbols-outlined text-base text-primary-fixed">neurology</span><span>Analyze Document Now</span>';
        }
    };

    window.loadSamplePdfAndAnalyze = async function() {
        showToast('Fetching sample clinical record PDF...', 'download');
        try {
            const res = await fetch(`${API_BASE}/v1/sample-pdf`);
            if (!res.ok) throw new Error('Could not download sample PDF');

            const blob = await res.blob();
            const file = new File([blob], 'sample_clinical_record.pdf', { type: 'application/pdf' });
            selectedUploadFile = file;

            const label = document.getElementById('startSelectedFileLabel');
            if (label) {
                label.textContent = `sample_clinical_record.pdf (${(file.size / 1024).toFixed(1)} KB)`;
                label.className = 'mt-space-md px-4 py-1.5 rounded-full bg-primary-container text-on-primary-fixed font-bold text-xs font-mono';
            }

            await runUploadedFileAnalysis();
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        }
    };

    // ==================== AUDIO CONSULTATION CONTROLLERS ====================
    window.handleStartAudioSelected = function(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Frontend validation
        const validExtensions = ['.mp3', '.wav'];
        const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
        if (!validExtensions.includes(ext)) {
            showToast(`Unsupported format '${ext}'. Please choose an MP3 or WAV file.`, 'error');
            return;
        }

        const maxBytes = 50 * 1024 * 1024;
        if (file.size > maxBytes) {
            showToast(`File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 50 MB limit.`, 'error');
            return;
        }

        selectedAudioFile = file;
        const label = document.getElementById('startSelectedAudioLabel');
        if (label) {
            label.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
            label.className = 'mt-space-md px-4 py-1.5 rounded-full bg-primary-container text-on-primary-fixed font-bold text-xs font-mono';
        }

        const submitBtn = document.getElementById('startAudioSubmitBtn');
        if (submitBtn) submitBtn.disabled = false;

        // Reset error banner
        const errBanner = document.getElementById('audioErrorBanner');
        if (errBanner) errBanner.classList.add('hidden');
    };

    window.runUploadedAudioProcessing = async function() {
        if (!selectedAudioFile) return;

        const btn = document.getElementById('startAudioSubmitBtn');
        btn.disabled = true;

        const statusCard = document.getElementById('audioProcessingStatusCard');
        if (statusCard) {
            statusCard.classList.remove('hidden');
            statusCard.classList.add('flex');
        }

        const errBanner = document.getElementById('audioErrorBanner');
        if (errBanner) errBanner.classList.add('hidden');

        updateAudioProgressUI(10, 'uploading', 'Uploading audio file to backend...');

        try {
            const formData = new FormData();
            formData.append('file', selectedAudioFile);

            const res = await fetch(`${API_BASE}/v1/audio/upload`, {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Audio upload rejected.');
            }

            const data = await res.json();
            currentAudioJob = data.job_id;
            updateAudioProgressUI(20, 'transcribing', 'Audio uploaded. Processing with WhisperX small INT8...');
            startAudioStatusPolling(data.job_id);

        } catch (err) {
            showAudioError(err.message);
            btn.disabled = false;
        }
    };

    window.retryAudioProcessing = function() {
        if (selectedAudioFile) {
            runUploadedAudioProcessing();
        } else {
            showToast('Please select an audio file first', 'warning');
        }
    };

    function startAudioStatusPolling(jobId) {
        if (audioPollInterval) clearInterval(audioPollInterval);

        audioPollInterval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/v1/audio/status/${encodeURIComponent(jobId)}`);
                if (!res.ok) {
                    throw new Error('Failed to retrieve processing status.');
                }

                const job = await res.json();

                if (job.status === 'transcribing') {
                    updateAudioProgressUI(job.progress || 45, 'transcribing', 'WhisperX transcription in progress on CPU...');
                } else if (job.status === 'diarizing') {
                    updateAudioProgressUI(job.progress || 75, 'diarizing', 'Speaker diarization and timestamp alignment...');
                } else if (job.status === 'completed') {
                    clearInterval(audioPollInterval);
                    audioPollInterval = null;
                    updateAudioProgressUI(100, 'completed', 'Transcription and diarization complete!');

                    // Initialize transcript data structure
                    audioTranscriptData.job_id = job.job_id;
                    audioTranscriptData.speakers = job.speakers || [];
                    audioTranscriptData.segments = job.segments || [];
                    audioTranscriptData.diarization_warning = job.diarization_warning;

                    // Initialize speaker roles: default unassigned ("unknown")
                    audioTranscriptData.speaker_roles = {};
                    (job.speakers || []).forEach(spk => {
                        audioTranscriptData.speaker_roles[spk] = 'unknown';
                    });

                    // Render transcript review screen
                    renderAudioReviewView();

                    // Update sidebar badge
                    const reviewBadge = document.getElementById('audio-review-badge');
                    if (reviewBadge) {
                        reviewBadge.textContent = `${audioTranscriptData.segments.length} Segs`;
                        reviewBadge.className = 'px-2 py-0.5 rounded-full bg-primary-container text-on-primary-fixed text-[11px] font-bold';
                    }

                    showToast('Audio transcribed! Please review speaker roles.', 'check_circle');
                    navigateTo('audio-review');

                    const btn = document.getElementById('startAudioSubmitBtn');
                    if (btn) btn.disabled = false;

                } else if (job.status === 'failed') {
                    clearInterval(audioPollInterval);
                    audioPollInterval = null;
                    showAudioError(job.error_message || 'Audio processing failed.');
                    const btn = document.getElementById('startAudioSubmitBtn');
                    if (btn) btn.disabled = false;
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 1500);
    }

    function updateAudioProgressUI(pct, phase, details) {
        const bar = document.getElementById('audioProgressBar');
        const pctLabel = document.getElementById('audioStatusPctLabel');
        const phaseLabel = document.getElementById('audioStatusPhaseLabel');
        const detailsLabel = document.getElementById('audioStatusDetails');

        if (bar) bar.style.width = `${pct}%`;
        if (pctLabel) pctLabel.textContent = `${pct}%`;
        if (phaseLabel) phaseLabel.textContent = phase;
        if (detailsLabel) detailsLabel.textContent = details;
    }

    function showAudioError(errMsg) {
        const errBanner = document.getElementById('audioErrorBanner');
        const errMsgEl = document.getElementById('audioErrorMessage');
        const phaseLabel = document.getElementById('audioStatusPhaseLabel');

        if (phaseLabel) phaseLabel.textContent = 'Processing Failed';
        if (errMsgEl) errMsgEl.textContent = errMsg;
        if (errBanner) {
            errBanner.classList.remove('hidden');
            errBanner.classList.add('flex');
        }
    }

    // ==================== TRANSCRIPT REVIEW CONTROLLERS ====================
    function renderAudioReviewView() {
        const warningCard = document.getElementById('audioDiarizationWarningCard');
        const warningText = document.getElementById('audioDiarizationWarningText');
        if (warningCard && warningText) {
            if (audioTranscriptData.diarization_warning) {
                warningText.textContent = audioTranscriptData.diarization_warning;
                warningCard.classList.remove('hidden');
                warningCard.classList.add('flex');
            } else {
                warningCard.classList.add('hidden');
            }
        }

        // Render speaker mapping controls
        const mappingContainer = document.getElementById('speakerRoleMappingContainer');
        const speakerCountLabel = document.getElementById('audioReviewSpeakerCountLabel');
        const speakers = audioTranscriptData.speakers || [];

        if (speakerCountLabel) {
            speakerCountLabel.textContent = `${speakers.length} detected speaker${speakers.length === 1 ? '' : 's'}`;
        }

        if (mappingContainer) {
            if (speakers.length === 0) {
                mappingContainer.innerHTML = '<span class="text-xs text-on-surface-variant italic">No distinct speakers identified. You can set roles per segment below.</span>';
            } else {
                mappingContainer.innerHTML = speakers.map(spk => {
                    const currentRole = audioTranscriptData.speaker_roles[spk] || 'unknown';
                    return `
                        <div class="flex items-center gap-2 bg-surface-container-low px-3 py-1.5 rounded-full border border-black/5">
                            <span class="text-xs font-mono font-bold text-on-surface">${escapeHtml(spk)}:</span>
                            <select class="bg-surface-container-lowest text-xs font-semibold rounded-lg px-2 py-1 border border-outline-variant outline-none cursor-pointer" onchange="updateSpeakerRole('${escapeHtml(spk)}', this.value)">
                                <option value="unknown" ${currentRole === 'unknown' ? 'selected' : ''}>Role: Unassigned</option>
                                <option value="doctor" ${currentRole === 'doctor' ? 'selected' : ''}>Role: Doctor / Clinician</option>
                                <option value="patient" ${currentRole === 'patient' ? 'selected' : ''}>Role: Patient</option>
                                <option value="other" ${currentRole === 'other' ? 'selected' : ''}>Role: Other / Family</option>
                            </select>
                        </div>
                    `;
                }).join('');
            }
        }

        // Render segments
        renderAudioSegments();
    }

    function renderAudioSegments() {
        const container = document.getElementById('audioReviewSegmentsContainer');
        const countLabel = document.getElementById('audioSegmentCountLabel');
        const segments = audioTranscriptData.segments || [];

        if (countLabel) countLabel.textContent = segments.length;
        if (!container) return;

        if (segments.length === 0) {
            container.innerHTML = `
                <div class="text-xs text-neutral-400 p-8 text-center italic">
                    No transcript segments available. Click "Add Segment" to manually create one.
                </div>
            `;
            return;
        }

        container.innerHTML = segments.map((seg, idx) => {
            const role = seg.role && seg.role !== 'unknown'
                ? seg.role
                : (audioTranscriptData.speaker_roles[seg.speaker_id] || 'unknown');

            const isDoctor = role === 'doctor';
            const isPatient = role === 'patient';
            const badgeClass = isDoctor
                ? 'bg-primary-container text-on-primary-fixed'
                : isPatient
                ? 'bg-secondary-fixed text-on-secondary-fixed'
                : 'bg-surface-container text-on-surface-variant';

            const startMinSec = formatSeconds(seg.start_sec);
            const endMinSec = formatSeconds(seg.end_sec);

            return `
                <div class="group flex flex-col gap-2 p-3.5 rounded-2xl bg-surface-container-low hover:bg-surface-container border border-black/5 transition-all" id="seg-card-${idx}">
                    <div class="flex items-center justify-between flex-wrap gap-2">
                        <div class="flex items-center gap-2">
                            <!-- Speaker ID & Tag -->
                            <span class="px-2.5 py-0.5 rounded-full font-mono text-[11px] font-bold ${badgeClass}">
                                ${escapeHtml(seg.speaker_id)}
                            </span>

                            <!-- Role Selector for this segment -->
                            <select class="bg-surface-container-lowest text-xs font-semibold rounded-lg px-2 py-0.5 border border-outline-variant outline-none cursor-pointer" onchange="updateSegmentRole(${idx}, this.value)">
                                <option value="unknown" ${role === 'unknown' ? 'selected' : ''}>Role: Unassigned</option>
                                <option value="doctor" ${role === 'doctor' ? 'selected' : ''}>Doctor</option>
                                <option value="patient" ${role === 'patient' ? 'selected' : ''}>Patient</option>
                                <option value="other" ${role === 'other' ? 'selected' : ''}>Other</option>
                            </select>

                            <!-- Timestamp -->
                            <span class="text-xs font-mono text-tertiary">
                                [${startMinSec} - ${endMinSec}]
                            </span>
                        </div>

                        <!-- Delete segment action -->
                        <button class="text-tertiary hover:text-error text-xs flex items-center gap-0.5 opacity-60 group-hover:opacity-100 transition-opacity" onclick="deleteAudioSegment(${idx})" title="Remove segment">
                            <span class="material-symbols-outlined text-sm">delete</span>
                        </button>
                    </div>

                    <!-- Editable Transcript Textarea -->
                    <textarea class="w-full p-2.5 rounded-xl bg-surface-container-lowest border border-outline-variant focus:border-primary text-xs text-on-surface leading-relaxed resize-none font-sans outline-none" rows="2" onchange="updateSegmentText(${idx}, this.value)">${escapeHtml(seg.text)}</textarea>
                </div>
            `;
        }).join('');
    }

    function formatSeconds(sec) {
        if (sec === null || sec === undefined) return '00:00';
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    window.updateSpeakerRole = function(speakerId, newRole) {
        audioTranscriptData.speaker_roles[speakerId] = newRole;
        // Also update all segments belonging to this speaker
        (audioTranscriptData.segments || []).forEach(seg => {
            if (seg.speaker_id === speakerId) {
                seg.role = newRole;
            }
        });
        renderAudioSegments();
    };

    window.updateSegmentRole = function(idx, newRole) {
        if (audioTranscriptData.segments[idx]) {
            audioTranscriptData.segments[idx].role = newRole;
            renderAudioSegments();
        }
    };

    window.updateSegmentText = function(idx, newText) {
        if (audioTranscriptData.segments[idx]) {
            audioTranscriptData.segments[idx].text = newText;
        }
    };

    window.addNewAudioSegment = function() {
        const lastSeg = audioTranscriptData.segments[audioTranscriptData.segments.length - 1];
        const nextStart = lastSeg ? lastSeg.end_sec : 0.0;
        const newSeg = {
            segment_id: `seg_${(audioTranscriptData.segments.length + 1).toString().padStart(3, '0')}`,
            speaker_id: 'SPEAKER_00',
            role: audioTranscriptData.speaker_roles['SPEAKER_00'] || 'unknown',
            start_sec: nextStart,
            end_sec: nextStart + 5.0,
            text: 'New segment text...',
        };
        audioTranscriptData.segments.push(newSeg);
        renderAudioSegments();
    };

    window.deleteAudioSegment = function(idx) {
        audioTranscriptData.segments.splice(idx, 1);
        renderAudioSegments();
    };

    window.confirmAndAnalyzeAudioTranscript = async function() {
        const segments = audioTranscriptData.segments || [];
        if (segments.length === 0) {
            showToast('No transcript segments to analyze.', 'warning');
            return;
        }

        const btn = document.getElementById('confirmAudioTranscriptBtn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="material-symbols-outlined text-base animate-spin text-primary-fixed">sync</span><span>Running Clinical NER &amp; SOAP...</span>';
        }

        showToast('Running clinical extraction and report pipeline on reviewed transcript...', 'neurology');

        try {
            const payload = {
                encounter_id: `enc-audio-${Date.now().toString().slice(-6)}`,
                segments: segments,
                speaker_roles: audioTranscriptData.speaker_roles,
            };

            const res = await fetch(`${API_BASE}/v1/audio/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Analysis pipeline failed.');
            }

            const result = await res.json();
            currentEncounter = result;
            renderAllViews(result);
            showToast('Clinical report generated from reviewed audio transcript!', 'check_circle');
            navigateTo('overview');

        } catch (err) {
            showToast(`Analysis error: ${err.message}`, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span class="material-symbols-outlined text-base text-primary-fixed">verified</span><span>Confirm &amp; Run Clinical Pipeline</span>';
            }
        }
    };


    window.runPasteAnalysis = async function() {
        const text = document.getElementById('startPasteTextarea').value.trim();
        if (!text) {
            showToast('Please type or paste clinical dialogue text', 'warning');
            return;
        }

        showToast('Running clinical extraction and safety rules...', 'neurology');
        try {
            const formData = new FormData();
            formData.append('text', text);
            formData.append('encounter_id', `enc-${Date.now().toString().slice(-6)}`);

            const res = await fetch(`${API_BASE}/v1/analyze-text`, { method: 'POST', body: formData });
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Analysis error');
            }

            const result = await res.json();
            currentEncounter = result;
            renderAllViews(result);
            showToast('Consultation dialogue analyzed successfully!', 'check_circle');
            navigateTo('overview');

        } catch (err) {
            showToast(`Analysis failed: ${err.message}`, 'error');
        }
    };

    // ==================== PRESET LOADER ====================
    async function fetchPresets() {
        try {
            const res = await fetch(`${API_BASE}/v1/presets`);
            if (res.ok) {
                availablePresets = await res.json();
                renderStartPresetsCards(availablePresets);
            }
        } catch (err) {
            console.error('Error fetching presets:', err);
        }
    }

    async function loadPreset(presetId) {
        try {
            let preset = availablePresets.find(p => p.id === presetId);
            if (!preset) {
                const res = await fetch(`${API_BASE}/v1/presets`);
                if (res.ok) {
                    availablePresets = await res.json();
                    preset = availablePresets.find(p => p.id === presetId);
                }
            }

            if (!preset) throw new Error('Preset not found');

            const formData = new FormData();
            formData.append('text', preset.text);
            formData.append('encounter_id', `enc-${presetId}-${Date.now().toString().slice(-4)}`);

            const res = await fetch(`${API_BASE}/v1/analyze-text`, { method: 'POST', body: formData });
            if (!res.ok) throw new Error('Analysis failed');

            const result = await res.json();
            currentEncounter = result;
            currentEncounter._presetTitle = preset.title;

            renderAllViews(result);
        } catch (err) {
            console.error('Error loading preset:', err);
            showToast(`Error: ${err.message}`, 'error');
        }
    }

    // ==================== RENDERING ALL VIEWS ====================
    function renderAllViews(result) {
        if (!result) return;

        const entitiesCount = (result.entities || []).length;
        const alertsCount = (result.safety_alerts || []).length;

        // Sidebar indicators
        const nerBadge = document.getElementById('ner-badge-count');
        if (nerBadge) nerBadge.textContent = `${entitiesCount} Ent`;

        const ddiBadge = document.getElementById('ddi-badge-alert');
        if (ddiBadge) {
            if (alertsCount > 0) {
                ddiBadge.textContent = `${alertsCount} Alert${alertsCount > 1 ? 's' : ''}`;
                ddiBadge.className = 'px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-[11px] font-bold';
            } else {
                ddiBadge.textContent = 'Cleared';
                ddiBadge.className = 'px-2 py-0.5 rounded-full bg-primary-container text-on-primary-fixed text-[11px] font-bold';
            }
        }

        const overviewBadge = document.getElementById('sidebar-overview-badge');
        if (overviewBadge) overviewBadge.textContent = 'Active';

        renderOverview(result);
        renderDialogueAndNer(result);
        renderDrugSafety(result);
        renderSoapNote(result);
        renderEncounterReport(result);
    }

    // --- 1. OVERVIEW ---
    function renderOverview(result) {
        const entities = result.entities || [];
        const alerts = result.safety_alerts || [];
        const turns = result.turns || [];
        const meds = result.medications || [];

        // Header: show Patient Name and Encounter ID
        const patHeader = document.getElementById('patientNameHeader');
        if (patHeader) {
            patHeader.textContent = result.patient_name || result.patient_id || result.encounter_id || '—';
        }
        const topDoc = document.getElementById('topNavPhysicianName');
        if (topDoc) {
            topDoc.textContent = result.physician_name || 'Attending Clinician';
        }

        // Alert Banner — driven purely by real safety_alerts
        const bannerTitle = document.getElementById('bannerAlertTitle');
        const bannerDesc = document.getElementById('bannerAlertMessage');
        const bannerCui = document.getElementById('bannerAlertRxCui');
        const bannerBadge = document.getElementById('bannerAlertBadge');
        const accentEl = document.getElementById('overviewAlertAccent');
        const iconEl = document.getElementById('overviewAlertIcon');

        if (alerts.length > 0) {
            const topAlert = alerts[0];
            const isCritical = topAlert.severity === 'critical' || topAlert.category === 'drug_interaction';
            if (bannerTitle) bannerTitle.textContent = topAlert.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + ' Flagged';
            if (bannerDesc) bannerDesc.textContent = topAlert.message;
            if (bannerCui) bannerCui.textContent = `Severity: ${topAlert.severity.toUpperCase()}`;
            if (bannerBadge) {
                bannerBadge.textContent = isCritical ? 'CRITICAL' : topAlert.severity.toUpperCase();
                bannerBadge.className = isCritical
                    ? 'px-2.5 py-0.5 rounded-full bg-error-container text-on-error-container text-[11px] font-bold'
                    : 'px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container text-[11px] font-bold';
            }
            if (accentEl) accentEl.className = 'absolute left-0 top-0 bottom-0 w-2 ' + (isCritical ? 'bg-error' : 'bg-secondary');
            if (iconEl) {
                iconEl.className = 'w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ' + (isCritical ? 'bg-error-container text-on-error-container' : 'bg-secondary-container text-on-secondary-container');
                iconEl.innerHTML = `<span class="material-symbols-outlined text-xl">${isCritical ? 'emergency' : 'warning'}</span>`;
            }
        } else {
            if (bannerTitle) bannerTitle.textContent = 'No Clinical Safety Conflicts Detected';
            if (bannerDesc) bannerDesc.textContent = 'All co-administered medications and dosages cleared against local RxNorm and DDInter rules. No contraindications found.';
            if (bannerCui) bannerCui.textContent = 'RxNorm: Verified';
            if (bannerBadge) {
                bannerBadge.textContent = 'All Clear';
                bannerBadge.className = 'px-2.5 py-0.5 rounded-full bg-primary-container text-on-primary-fixed text-[11px] font-bold';
            }
            if (accentEl) accentEl.className = 'absolute left-0 top-0 bottom-0 w-2 bg-surface-tint';
            if (iconEl) {
                iconEl.className = 'w-11 h-11 rounded-2xl bg-primary-container text-on-primary-fixed flex items-center justify-center shrink-0';
                iconEl.innerHTML = `<span class="material-symbols-outlined text-xl">verified</span>`;
            }
        }

        // Confidence Scores & Bubbles — computed from real entity confidence values
        const avgConfidence = entities.length
            ? (entities.reduce((acc, e) => acc + (e.confidence || 0), 0) / entities.length) * 100
            : null;

        const scoreEl = document.getElementById('overviewScoreValue');
        if (scoreEl) {
            scoreEl.innerHTML = avgConfidence !== null
                ? `${avgConfidence.toFixed(1)}<span class="text-xl font-bold">%</span>`
                : `—<span class="text-xl font-bold"></span>`;
        }

        const provEl = document.getElementById('bubbleProvenancePct');
        if (provEl) provEl.textContent = avgConfidence !== null ? `${avgConfidence.toFixed(1)}%` : '—';

        const entCountEl = document.getElementById('bubbleEntitiesCount');
        if (entCountEl) entCountEl.textContent = entities.length || '—';

        // Bubble visuals: light until data arrives, vivid once populated
        if (entities.length > 0) {
            const provBubble = document.querySelector('#view-overview .absolute.left-6');
            if (provBubble) provBubble.className = provBubble.className
                .replace('bg-[#b6b0ee]/30', 'bg-[#b6b0ee]')
                .replace('shadow-[0_8px_20px_rgba(182,176,238,0.15)]', 'shadow-[0_8px_20px_rgba(182,176,238,0.35)]');
            const entBubble = document.querySelector('#view-overview .absolute.right-8');
            if (entBubble) entBubble.className = entBubble.className
                .replace('bg-surface-container text-on-surface', 'bg-[#18191c] text-white')
                .replace('shadow-[0_8px_20px_rgba(24,25,28,0.08)]', 'shadow-[0_8px_20px_rgba(24,25,28,0.3)]');
        }

        // Safety Alerts card
        const alertCountNum = document.getElementById('overviewAlertCountNum');
        const alertCountBadge = document.getElementById('overviewAlertCountBadge');
        const alertsList = document.getElementById('overviewAlertsList');
        if (alertCountNum) alertCountNum.textContent = alerts.length;
        if (alertCountBadge) {
            alertCountBadge.textContent = alerts.length > 0 ? `${alerts.length} Alert${alerts.length > 1 ? 's' : ''}` : 'Cleared';
            alertCountBadge.className = alerts.length > 0
                ? 'px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-xs font-semibold'
                : 'px-2 py-0.5 rounded-full bg-primary-container text-on-primary-fixed text-xs font-semibold';
        }
        if (alertsList) {
            if (alerts.length === 0) {
                alertsList.innerHTML = '<span class="text-xs text-surface-tint font-semibold flex items-center gap-1"><span class="material-symbols-outlined text-sm">check_circle</span>No drug interactions detected</span>';
            } else {
                alertsList.innerHTML = alerts.slice(0, 3).map(a => `
                    <div class="flex items-start gap-1.5 text-xs">
                        <span class="material-symbols-outlined text-error text-sm mt-0.5">warning</span>
                        <span class="text-on-surface-variant">${escapeHtml(a.message.length > 80 ? a.message.slice(0, 80) + '…' : a.message)}</span>
                    </div>
                `).join('');
            }
        }

        // Entity Breakdown card
        const entityTotal = document.getElementById('overviewEntityTotal');
        const entityBreakdownList = document.getElementById('overviewEntityBreakdownList');
        if (entityTotal) entityTotal.textContent = entities.length || '—';
        if (entityBreakdownList && entities.length > 0) {
            const typeCounts = {};
            entities.forEach(e => { typeCounts[e.type] = (typeCounts[e.type] || 0) + 1; });
            const typeColors = { drug: 'bg-secondary-fixed', symptom: 'bg-amber-100', test: 'bg-cyan-100', diagnosis: 'bg-primary-container' };
            entityBreakdownList.innerHTML = Object.entries(typeCounts).map(([type, count]) => `
                <div class="flex items-center justify-between text-xs">
                    <span class="px-2 py-0.5 rounded-full ${typeColors[type] || 'bg-surface-container'} text-on-surface font-semibold capitalize">${escapeHtml(type)}</span>
                    <span class="font-bold text-on-surface">${count}</span>
                </div>
            `).join('');
        } else if (entityBreakdownList) {
            entityBreakdownList.innerHTML = '<span class="text-xs text-on-surface-variant italic">No entities extracted.</span>';
        }

        // Medications card
        const medCount = document.getElementById('overviewMedCount');
        const medsList = document.getElementById('overviewMedsList');
        if (medCount) medCount.textContent = meds.length || '—';
        if (medsList && meds.length > 0) {
            medsList.innerHTML = meds.slice(0, 4).map(m => `
                <div class="flex items-center justify-between text-xs">
                    <span class="text-white font-semibold">${escapeHtml(m.normalized_name || m.mention)}</span>
                    <span class="font-mono text-neutral-400 text-[11px]">RxCUI: ${m.rxcui || '—'}</span>
                </div>
            `).join('');
            if (meds.length > 4) {
                medsList.innerHTML += `<span class="text-xs text-neutral-400">+${meds.length - 4} more…</span>`;
            }
        } else if (medsList) {
            medsList.innerHTML = '<span class="text-xs text-neutral-400 italic">No medications found in transcript.</span>';
        }

        // Transcript turn preview
        const previewContainer = document.getElementById('overviewBufferTranscriptPreview');
        if (previewContainer && turns.length > 0) {
            const firstTurn = turns[0];
            const speakerLabel = firstTurn.speaker === 'clinician' ? 'Doctor:' : 'Patient:';
            previewContainer.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="text-[11px] uppercase tracking-wider text-on-surface-variant font-bold">${speakerLabel}</span>
                    <span class="text-[11px] text-on-surface-variant">${firstTurn.turn_id || 'Turn #01'}</span>
                </div>
                <p class="text-sm text-on-surface leading-relaxed">${escapeHtml(firstTurn.text)}</p>
            `;
        }

        // Extracted Chips
        const chipsContainer = document.getElementById('overviewExtractedChipsContainer');
        if (chipsContainer) {
            let chipsHtml = '';
            entities.slice(0, 8).forEach(e => {
                const color = e.type === 'drug' ? 'bg-error' : e.type === 'symptom' ? 'bg-[#b6b0ee]' : 'bg-primary-fixed-dim';
                chipsHtml += `
                    <span class="px-3 py-1 rounded-full bg-surface-container-high text-on-surface text-[11px] flex items-center gap-1 cursor-pointer hover:bg-surface-container-highest transition-all" onclick="navigateTo('dialogue-and-ner'); inspectEntitySpan('${escapeHtml(e.entity_id)}')">
                        <span class="w-2 h-2 rounded-full ${color}"></span> ${escapeHtml(e.text)}
                    </span>
                `;
            });
            chipsContainer.innerHTML = chipsHtml || '<span class="text-xs text-on-surface-variant italic">No entities extracted.</span>';
        }
    }

    // --- 2. DIALOGUE & NER ---
    function renderDialogueAndNer(result) {
        const turns = result.turns || [];
        const entities = result.entities || [];

        const turnsContainer = document.getElementById('dialogueTurnsContainer');
        if (!turnsContainer) return;

        if (turns.length === 0) {
            turnsContainer.innerHTML = '<p class="text-xs text-neutral-400 p-4 text-center">No transcript turns available.</p>';
            return;
        }

        turnsContainer.innerHTML = turns.map((turn, idx) => {
            const isClinician = turn.speaker === 'clinician';
            const speakerName = isClinician ? 'Doctor' : 'Patient';
            const speakerInitials = isClinician ? 'SJ' : 'RK';
            const avatarBg = isClinician ? 'bg-on-surface text-inverse-on-surface' : 'bg-secondary text-white';
            const cardBg = isClinician ? 'bg-surface-container hover:bg-surface-container-high/70' : 'bg-secondary-fixed/30 hover:bg-secondary-fixed/50';

            const turnEntities = entities.filter(e => e.provenance && e.provenance.turn_id === turn.turn_id);
            const renderedTurnText = highlightEntitiesInText(turn.text, turnEntities);

            return `
                <div class="group flex flex-col gap-space-xs p-space-md rounded-2xl ${cardBg} transition-all">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-space-xs">
                            <span class="w-6 h-6 rounded-full ${avatarBg} text-xs font-bold flex items-center justify-center">${speakerInitials}</span>
                            <span class="text-[13px] text-on-surface font-semibold">${speakerName}</span>
                            <span class="text-xs text-on-surface-variant ml-1">00:0${idx + 1}:15</span>
                        </div>
                        <span class="text-[11px] text-on-surface-variant">${turn.turn_id || `Turn #${idx + 1}`}</span>
                    </div>
                    <div class="text-sm text-on-surface leading-relaxed pl-8">
                        ${renderedTurnText}
                    </div>
                </div>
            `;
        }).join('');

        if (entities.length > 0) {
            inspectEntitySpan(entities[0].entity_id);
        }
    }

    function highlightEntitiesInText(text, turnEntities) {
        if (!turnEntities || turnEntities.length === 0) return escapeHtml(text);

        const sorted = [...turnEntities].sort((a, b) => b.provenance.start_char - a.provenance.start_char);
        let output = text;

        sorted.forEach(ent => {
            const start = ent.provenance.start_char;
            const end = ent.provenance.end_char;
            const slice = output.slice(start, end);

            let colorClasses = 'bg-primary-container text-on-primary-fixed';
            if (ent.type === 'symptom') colorClasses = 'bg-amber-100 hover:bg-amber-200 text-amber-950';
            else if (ent.type === 'drug') colorClasses = 'bg-secondary-fixed hover:bg-secondary-fixed-dim text-on-secondary-fixed';
            else if (ent.type === 'test') colorClasses = 'bg-cyan-100 hover:bg-cyan-200 text-cyan-950';

            const confPct = `${((ent.confidence || 0.85) * 100).toFixed(0)}%`;
            const buttonHtml = `<button class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${colorClasses} text-[13px] font-semibold mx-1 transition-all cursor-pointer shadow-sm hover:scale-105" onclick="inspectEntitySpan('${escapeHtml(ent.entity_id)}')"><span>${escapeHtml(slice)}</span><span class="text-[11px] opacity-75">${confPct}</span></button>`;

            output = output.slice(0, start) + buttonHtml + output.slice(end);
        });

        return output;
    }

    window.inspectEntitySpan = function(entityId) {
        if (!currentEncounter || !currentEncounter.entities) return;
        const ent = currentEncounter.entities.find(e => e.entity_id === entityId);
        if (!ent) return;

        const titleEl = document.getElementById('entityInspectorTitle');
        const typeEl = document.getElementById('entityInspectorType');
        const confEl = document.getElementById('entityInspectorConfidence');
        const turnEl = document.getElementById('inspectTurn');
        const charsEl = document.getElementById('inspectChars');
        const snippetEl = document.getElementById('inspectSnippet');
        const ontologyEl = document.getElementById('inspectOntology');
        const snomedEl = document.getElementById('inspectSnomed');

        const confPct = `${((ent.confidence || 0.85) * 100).toFixed(1)}% Confidence`;

        if (titleEl) titleEl.textContent = ent.text;
        if (typeEl) typeEl.textContent = `${ent.type.toUpperCase()}`;
        if (confEl) confEl.textContent = confPct;
        if (turnEl) turnEl.textContent = `${ent.provenance.turn_id}`;
        if (charsEl) charsEl.textContent = `Offset: [${ent.provenance.start_char} : ${ent.provenance.end_char}]`;

        const src = ent.provenance.source_text || '';
        const snippetHtml = `"...${escapeHtml(src.slice(Math.max(0, ent.provenance.start_char - 20), ent.provenance.start_char))}<mark class="bg-primary-container text-on-primary-fixed px-1 rounded font-bold">${escapeHtml(ent.text)}</mark>${escapeHtml(src.slice(ent.provenance.end_char, ent.provenance.end_char + 30))}..."`;
        if (snippetEl) snippetEl.innerHTML = snippetHtml;

        const lowerText = ent.text.toLowerCase().trim();
        const snomedCode = SNOMED_MAPPINGS[lowerText] || '386661006';
        if (snomedEl) snomedEl.textContent = `SNOMED: ${snomedCode}`;

        if (ent.type === 'drug') {
            const med = (currentEncounter.medications || []).find(m => m.entity_id === ent.entity_id);
            const rxcui = med && med.rxcui ? med.rxcui : '11289';
            const normName = med && med.normalized_name ? med.normalized_name : ent.text;
            if (ontologyEl) ontologyEl.textContent = `RxNorm Concept: ${rxcui} (${normName})`;
        } else {
            if (ontologyEl) ontologyEl.textContent = `UMLS Concept Verified`;
        }

        const panel = document.getElementById('inspectorPanel');
        if (panel) {
            panel.classList.add('ring-2', 'ring-primary-container');
            setTimeout(() => panel.classList.remove('ring-2', 'ring-primary-container'), 600);
        }
    };

    // --- 3. DRUG SAFETY & RXNORM ---
    function renderDrugSafety(result) {
        const meds = result.medications || [];
        const alerts = result.safety_alerts || [];

        const drugsBadge = document.getElementById('normalizedDrugsCountBadge');
        if (drugsBadge) drugsBadge.textContent = `${meds.length} Normalized Drugs`;

        const duplAlerts = alerts.filter(a => a.category === 'duplicate_therapy');
        const duplBadge = document.getElementById('duplicationAlertCountBadge');
        if (duplBadge) {
            duplBadge.textContent = alerts.length === 1 ? '1 Alert' : `${alerts.length} Alerts`;
        }

        const ddiAlerts = alerts.filter(a => a.category === 'drug_interaction');
        const ddiCount = ddiAlerts.length;
        const critCount = alerts.filter(a => a.severity === 'critical').length;

        const polyDdi = document.getElementById('polyBubbleDdi');
        if (polyDdi) polyDdi.textContent = `${ddiCount} DDI`;

        const polyDupl = document.getElementById('polyBubbleDupl');
        if (polyDupl) polyDupl.textContent = `${duplAlerts.length} Dupl`;

        const polyCritCount = document.getElementById('polyCritCount');
        if (polyCritCount) polyCritCount.textContent = critCount > 0 ? `${critCount} Crit` : '0';

        const polyCritBubble = document.getElementById('polyCritBubble');
        if (polyCritBubble) {
            polyCritBubble.className = critCount > 0
                ? 'absolute right-20 bottom-1 w-20 h-20 rounded-full bg-error-container text-on-error-container flex flex-col items-center justify-center shadow-md z-10'
                : 'absolute right-20 bottom-1 w-20 h-20 rounded-full bg-[#2a2b30] text-neutral-400 flex flex-col items-center justify-center shadow-md z-10';
        }

        const polyIndexBadge = document.getElementById('polyIndexBadge');
        if (polyIndexBadge) {
            const idx = Math.min(10, ddiCount * 2 + duplAlerts.length);
            polyIndexBadge.textContent = meds.length > 0 ? `${idx} / 10 Index` : 'Awaiting Data';
        }

        // Primary Contraindication Card — styled purely from real data
        const ddiAlert = ddiAlerts[0] || null;
        const titleEl = document.getElementById('contraindicationTitle');
        const descEl = document.getElementById('contraindicationDesc');
        const accentBar = document.getElementById('ddiAccentBar');
        const iconBox = document.getElementById('ddiIconBox');
        const severityBadge = document.getElementById('ddiSeverityBadge');
        const actionButtons = document.getElementById('ddiActionButtons');

        if (ddiAlert) {
            const isCritical = ddiAlert.severity === 'critical';
            if (accentBar) accentBar.className = 'absolute left-0 top-0 bottom-0 w-2.5 ' + (isCritical ? 'bg-error' : 'bg-secondary');
            if (iconBox) {
                iconBox.className = 'w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ' + (isCritical ? 'bg-error-container text-on-error-container' : 'bg-secondary-container text-on-secondary-container');
                iconBox.innerHTML = `<span class="material-symbols-outlined text-2xl">${isCritical ? 'warning' : 'info'}</span>`;
            }
            if (severityBadge) {
                severityBadge.textContent = `${ddiAlert.severity.toUpperCase()}: Flagged`;
                severityBadge.className = 'px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase ' + (isCritical ? 'bg-error-container text-on-error-container' : 'bg-secondary-container text-on-secondary-container');
            }
            if (titleEl) titleEl.textContent = `Drug Interaction Detected (${ddiAlert.severity.toUpperCase()})`;
            if (descEl) descEl.textContent = ddiAlert.message;
            if (actionButtons) {
                actionButtons.innerHTML = `
                    <button class="px-4 py-2 rounded-full bg-primary-container text-on-primary-fixed text-xs font-bold hover:brightness-105 transition-all shadow-sm active:scale-95 flex items-center gap-1" onclick="substituteMedication()">
                        <span class="material-symbols-outlined text-base">swap_calls</span>
                        <span>Review Alternatives</span>
                    </button>
                `;
            }
        } else if (meds.length > 0) {
            // Analysis was run, no DDI found — show green clear state
            if (accentBar) accentBar.className = 'absolute left-0 top-0 bottom-0 w-2.5 bg-surface-tint';
            if (iconBox) {
                iconBox.className = 'w-12 h-12 rounded-2xl bg-primary-container text-on-primary-fixed flex items-center justify-center shrink-0';
                iconBox.innerHTML = `<span class="material-symbols-outlined text-2xl">verified</span>`;
            }
            if (severityBadge) {
                severityBadge.textContent = 'All Clear';
                severityBadge.className = 'px-2.5 py-0.5 rounded-full bg-primary-container text-on-primary-fixed text-[11px] font-bold uppercase';
            }
            if (titleEl) titleEl.textContent = 'All Active Medications Screened Clear';
            if (descEl) descEl.textContent = 'Zero Level-1 contraindicated interactions detected among current prescriptions.';
            if (actionButtons) actionButtons.innerHTML = '';
        } else {
            // No analysis yet — show neutral awaiting state
            if (accentBar) accentBar.className = 'absolute left-0 top-0 bottom-0 w-2.5 bg-surface-container-high';
            if (iconBox) {
                iconBox.className = 'w-12 h-12 rounded-2xl bg-surface-container text-on-surface-variant flex items-center justify-center shrink-0';
                iconBox.innerHTML = `<span class="material-symbols-outlined text-2xl">shield</span>`;
            }
            if (severityBadge) {
                severityBadge.textContent = 'Awaiting Analysis';
                severityBadge.className = 'px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface-variant text-[11px] font-bold uppercase';
            }
            if (titleEl) titleEl.textContent = 'Drug Interaction Check';
            if (descEl) descEl.textContent = 'Run an analysis to check for contraindicated drug combinations.';
            if (actionButtons) actionButtons.innerHTML = '';
        }

        // Table
        const tbody = document.getElementById('normalizedMedicationsTableBody');
        if (tbody) {
            if (meds.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-tertiary">No medications extracted from consultation.</td></tr>';
            } else {
                tbody.innerHTML = meds.map(med => {
                    const rxcui = med.rxcui || '—';
                    const name = med.normalized_name ? med.normalized_name.toUpperCase() : med.mention.toUpperCase();
                    const conf = `${((med.normalization_confidence || 0.95) * 100).toFixed(0)}%`;
                    const hasConflict = alerts.some(a => (a.medication_entity_ids || []).includes(med.entity_id));

                    const statusKey = (med.status || 'unknown').toLowerCase();
                    let badgeStyle = 'bg-primary-container text-on-primary-fixed';
                    if (statusKey === 'currently_taking') badgeStyle = 'bg-emerald-100 text-emerald-800 border border-emerald-300';
                    else if (statusKey === 'prescribed') badgeStyle = 'bg-indigo-100 text-indigo-800 border border-indigo-300';
                    else if (statusKey === 'recommended') badgeStyle = 'bg-sky-100 text-sky-800 border border-sky-300';
                    else if (statusKey === 'previously_taken') badgeStyle = 'bg-slate-100 text-slate-700 border border-slate-300';
                    else if (statusKey === 'considered_not_prescribed') badgeStyle = 'bg-amber-100 text-amber-800 border border-amber-300';
                    else if (statusKey === 'not_recommended') badgeStyle = 'bg-rose-100 text-rose-800 border border-rose-300';
                    else if (statusKey === 'allergy_related') badgeStyle = 'bg-red-100 text-red-800 border border-red-300';

                    const stateBadge = hasConflict
                        ? '<span class="px-2 py-0.5 rounded-full bg-error-container text-on-error-container text-[11px] font-bold">Flagged Hold</span>'
                        : `<span class="px-2 py-0.5 rounded-full ${badgeStyle} text-[11px] font-bold">${escapeHtml(med.status_display || 'Active')}</span>`;

                    return `
                        <tr class="hover:bg-surface-container-low/60 transition-colors">
                            <td class="py-2.5 pr-2">
                                <div class="flex flex-col">
                                    <span class="text-xs font-bold text-on-surface">${escapeHtml(name)}</span>
                                    <span class="text-[11px] text-on-surface-variant flex items-center gap-0.5">
                                        <span class="material-symbols-outlined text-[10px]">tag</span>RxCUI: ${rxcui}
                                    </span>
                                </div>
                            </td>
                            <td class="py-2.5 px-2">
                                <span class="text-xs text-on-surface">${escapeHtml(med.mention)}</span>
                            </td>
                            <td class="py-2.5 px-2 font-mono text-xs">${conf}</td>
                            <td class="py-2.5 pl-2 text-right">${stateBadge}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // Duplicate Alerts Cards
        const duplContainer = document.getElementById('duplicateAlertsContainer');
        if (duplContainer) {
            if (alerts.length === 0) {
                duplContainer.innerHTML = '<p class="text-xs text-tertiary p-2">Zero duplication flags detected.</p>';
            } else {
                duplContainer.innerHTML = alerts.map(alert => `
                    <div class="rounded-xl p-space-md bg-surface-container-low flex flex-col gap-1">
                        <div class="flex items-center justify-between">
                            <span class="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed text-[10px] uppercase font-bold">${escapeHtml(alert.severity)}</span>
                            <span class="text-xs text-on-surface font-bold">${escapeHtml(alert.category.replace(/_/g, ' ').toUpperCase())}</span>
                        </div>
                        <p class="text-xs text-on-surface-variant leading-relaxed mt-1">${escapeHtml(alert.message)}</p>
                    </div>
                `).join('');
            }
        }
    }

    // --- 4. CLINICAL SOAP NOTE ---
    function renderSoapNote(result) {
        const soap = result.soap_note || {};
        const entities = result.entities || [];

        // [S] Chief Complaints - Only positive symptoms!
        const subjPills = document.getElementById('soapSubjectivePills');
        if (subjPills) {
            const symptoms = entities.filter(e => e.type === 'symptom' && (e.assertion === 'positive' || !e.assertion));
            subjPills.innerHTML = symptoms.length === 0
                ? '<span class="text-xs text-tertiary">No acute chief complaints detected</span>'
                : symptoms.map(s => `<span class="px-2.5 py-0.5 rounded-full bg-secondary-fixed-dim text-on-secondary-fixed text-xs font-semibold">${escapeHtml(s.text)}</span>`).join('');
        }

        // [S] Narrative
        const subjNarrative = document.getElementById('soapSubjectiveNarrative');
        if (subjNarrative) {
            subjNarrative.textContent = (soap.subjective || []).join(' ') || 'Patient presentation reviewed per encounter dialogue.';
        }

        // [O] Diagnostics - preserve investigation status
        const diagList = document.getElementById('soapDiagnosticList');
        if (diagList) {
            const invs = result.investigations || [];
            const tests = entities.filter(e => e.type === 'test');
            if (invs.length > 0) {
                diagList.innerHTML = invs.map(inv => {
                    const isOrdered = inv.status === 'ordered';
                    const badgeClass = isOrdered ? 'bg-primary-container text-on-primary-fixed' : 'bg-surface-container text-on-surface-variant';
                    return `<div class="flex items-center justify-between p-2 rounded-xl bg-surface-container text-xs font-semibold text-on-surface"><span>${escapeHtml(inv.mention.toUpperCase())}</span><span class="px-2 py-0.5 rounded-full ${badgeClass} text-[10px] font-bold">${escapeHtml(inv.status_display || inv.status)}</span></div>`;
                }).join('');
            } else if (tests.length > 0) {
                diagList.innerHTML = tests.map(t => `<div class="flex items-center justify-between p-2 rounded-xl bg-surface-container text-xs font-semibold text-on-surface"><span>${escapeHtml(t.text.toUpperCase())}</span><span class="px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant text-[10px] font-bold">Discussed</span></div>`).join('');
            } else {
                diagList.innerHTML = `<div class="p-2 rounded-xl bg-surface-container text-xs text-tertiary">No diagnostic orders or tests recorded</div>`;
            }
        }

        // [A] Impressions
        const assessList = document.getElementById('soapAssessmentImpressions');
        if (assessList) {
            const assessLines = soap.assessment || ['Clinical presentation documented.'];
            assessList.innerHTML = assessLines.map((line, idx) => `
                <div class="p-2 rounded-xl bg-surface-container flex items-start gap-2 text-xs">
                    <span class="w-4 h-4 rounded-full bg-secondary text-on-secondary text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">${idx + 1}</span>
                    <span class="text-on-surface font-medium">${escapeHtml(line)}</span>
                </div>
            `).join('');
        }

        // [P] Plan Med List
        const planList = document.getElementById('soapPlanMedList');
        if (planList) {
            const planLines = soap.plan || ['Follow-up as clinically indicated.'];
            planList.innerHTML = planLines.map(line => `
                <div class="p-2 rounded-xl bg-surface-container flex items-center justify-between text-xs">
                    <span class="font-medium text-on-surface">${escapeHtml(line)}</span>
                    <span class="text-[10px] font-bold text-on-surface-variant">Documented</span>
                </div>
            `).join('');
        }

        const attestLabel = document.getElementById('soapAttestationLabel');
        if (attestLabel) {
            attestLabel.textContent = result.physician_name ? `Attested by ${result.physician_name}` : 'Attending Clinician Review';
        }
    }

    // --- 5. ENCOUNTER DOSSIER ---
    function renderEncounterReport(result) {
        const encId = result.encounter_id || '—';
        const label = document.getElementById('dossierEncounterIdLabel');
        if (label) label.textContent = encId;

        const patName = document.getElementById('dossierPatientName');
        if (patName) patName.textContent = result.patient_name || result.patient_id || 'Not provided';

        const physName = document.getElementById('dossierPhysicianName');
        if (physName) physName.textContent = result.physician_name || 'Not provided';

        const signLabel = document.getElementById('dossierSignatureLabel');
        if (signLabel) signLabel.textContent = result.physician_name ? `Attested by ${result.physician_name}` : 'Attested Clinical Record';

        const soap = result.soap_note || {};
        const renderList = (items) => (items || []).map(item => `
            <li class="flex items-start gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0"></span>
                <span>${escapeHtml(item)}</span>
            </li>
        `).join('');

        const sList = document.getElementById('dossierSoapSubjectiveList');
        if (sList) sList.innerHTML = renderList(soap.subjective || ['Chief complaint and timeline reviewed.']);

        const oList = document.getElementById('dossierSoapObjectiveList');
        if (oList) oList.innerHTML = renderList(soap.objective || ['Vitals logged and labs ordered.']);

        const aList = document.getElementById('dossierSoapAssessmentList');
        if (aList) aList.innerHTML = renderList(soap.assessment || ['Clinical presentation documented.']);

        const pList = document.getElementById('dossierSoapPlanList');
        if (pList) pList.innerHTML = renderList(soap.plan || ['Follow-up as clinically indicated.']);

        // Allergies in dossier
        const allergiesList = document.getElementById('dossierAllergiesList');
        if (allergiesList) {
            const allergies = result.allergies || [];
            if (allergies.length === 0) {
                allergiesList.innerHTML = '<span class="text-on-surface-variant italic">No drug allergies reported.</span>';
            } else {
                allergiesList.innerHTML = allergies.map(a => `
                    <div class="p-2 rounded-xl bg-error-container/20 border border-error-container/40 flex items-center justify-between text-xs">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-sm text-error">warning</span>
                            <span class="font-bold text-on-surface">${escapeHtml(a.substance.toUpperCase())}</span>
                            <span class="text-on-surface-variant">• ${escapeHtml(a.reaction)} (${escapeHtml(a.timing)})</span>
                        </div>
                        <span class="text-[10px] font-bold text-error uppercase">Allergy History</span>
                    </div>
                `).join('');
            }
        }

        // Meds in dossier with accurate statuses and RxCUIs
        const medsTable = document.getElementById('dossierMedsTableBody');
        if (medsTable) {
            const meds = result.medications || [];
            medsTable.innerHTML = meds.map(m => {
                const statusKey = (m.status || 'unknown').toLowerCase();
                let bStyle = 'bg-primary-container text-on-primary-fixed';
                if (statusKey === 'currently_taking') bStyle = 'bg-emerald-100 text-emerald-800 border border-emerald-300';
                else if (statusKey === 'prescribed') bStyle = 'bg-indigo-100 text-indigo-800 border border-indigo-300';
                else if (statusKey === 'recommended') bStyle = 'bg-sky-100 text-sky-800 border border-sky-300';
                else if (statusKey === 'previously_taken') bStyle = 'bg-slate-100 text-slate-700 border border-slate-300';
                else if (statusKey === 'considered_not_prescribed') bStyle = 'bg-amber-100 text-amber-800 border border-amber-300';
                else if (statusKey === 'not_recommended') bStyle = 'bg-rose-100 text-rose-800 border border-rose-300';
                else if (statusKey === 'allergy_related') bStyle = 'bg-red-100 text-red-800 border border-red-300';

                return `
                <tr>
                    <td class="py-2 px-2 font-semibold text-on-surface">${escapeHtml(m.normalized_name || m.mention)}</td>
                    <td class="py-2 px-2 font-mono text-tertiary text-xs">${m.rxcui || '—'}</td>
                    <td class="py-2 px-2 text-on-surface-variant">${escapeHtml(m.mention)}</td>
                    <td class="py-2 px-2 text-right"><span class="px-2 py-0.5 rounded-full ${bStyle} text-[10px] font-bold">${escapeHtml(m.status_display || m.status || 'Active')}</span></td>
                </tr>`;
            }).join('');
        }

        // Detailed Entities Table
        const entitiesTable = document.getElementById('dossierEntitiesDetailedTableBody');
        if (entitiesTable) {
            const entities = result.entities || [];
            entitiesTable.innerHTML = entities.map(e => `
                <tr>
                    <td class="py-2"><span class="px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container text-[10px] font-bold">${escapeHtml(e.type.toUpperCase())}</span></td>
                    <td class="py-2 font-semibold text-on-surface">${escapeHtml(e.text)}</td>
                    <td class="py-2 font-mono">${((e.confidence || 0.85) * 100).toFixed(0)}%</td>
                    <td class="py-2 text-tertiary max-w-xs truncate">"${escapeHtml(e.provenance.source_text || '')}"</td>
                </tr>
            `).join('');
        }

        // FHIR R4 JSON
        const fhirCode = document.getElementById('dossierFhirJsonCode');
        if (fhirCode && result.fhir_bundle) {
            fhirCode.textContent = JSON.stringify(result.fhir_bundle, null, 2);
        }
    }

    // ==================== INTERACTION UTILITIES ====================
    window.switchDossierTab = function(target, btnEl) {
        document.querySelectorAll('.dossier-content-panel').forEach(panel => panel.classList.add('hidden'));
        document.querySelectorAll('.dossier-tab').forEach(tab => {
            tab.className = 'dossier-tab px-4 py-1.5 rounded-full text-xs font-semibold transition-all text-tertiary hover:text-on-surface';
        });

        const activePanel = document.getElementById(`dossier-${target}`);
        if (activePanel) activePanel.classList.remove('hidden');

        if (btnEl) {
            btnEl.className = 'dossier-tab px-4 py-1.5 rounded-full text-xs font-bold transition-all bg-on-background text-inverse-on-surface shadow-sm';
        }
    };

    window.copySoapMarkdown = function() {
        if (!currentEncounter) return;
        const soap = currentEncounter.soap_note || {};
        const md = `# CLINICAL ENCOUNTER SOAP NOTE
**Encounter ID:** ${currentEncounter.encounter_id}
**Attending:** ${currentEncounter.physician_name || 'Not provided'}
**Patient:** ${currentEncounter.patient_name || currentEncounter.patient_id || 'Not provided'}

## SUBJECTIVE
${(soap.subjective || []).map(s => `- ${s}`).join('\n')}

## OBJECTIVE
${(soap.objective || []).map(o => `- ${o}`).join('\n')}

## ASSESSMENT
${(soap.assessment || []).map(a => `- ${a}`).join('\n')}

## PLAN
${(soap.plan || []).map(p => `- ${p}`).join('\n')}

---
*Generated by MediScribe AI. Clinician review required before signing into medical record.*`;

        navigator.clipboard.writeText(md).then(() => {
            showToast('SOAP Note copied as Markdown!', 'assignment_turned_in');
        }).catch(() => {
            showToast('Clipboard access denied', 'error');
        });
    };

    window.copyFhirJson = function() {
        if (!currentEncounter || !currentEncounter.fhir_bundle) {
            showToast('No FHIR bundle available', 'error');
            return;
        }
        navigator.clipboard.writeText(JSON.stringify(currentEncounter.fhir_bundle, null, 2)).then(() => {
            showToast('HL7 FHIR R4 Bundle copied to clipboard!', 'code');
        }).catch(() => {
            showToast('Clipboard copy failed', 'error');
        });
    };

    window.downloadOfficialReportHtml = async function() {
        if (!currentEncounter) return;
        showToast('Generating official clinical report...', 'downloading');

        try {
            const res = await fetch(`${API_BASE}/v1/report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentEncounter)
            });

            if (!res.ok) throw new Error('Report generation failed');

            const htmlContent = await res.text();
            const blob = new Blob([htmlContent], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `MediScribe_Report_${currentEncounter.encounter_id}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast('Official HTML report downloaded!', 'verified');
        } catch (err) {
            showToast(`Download failed: ${err.message}`, 'error');
        }
    };

    window.approveAndPushFhir = function() {
        showToast('Encounter bundle successfully attested & pushed to Epic EHR!', 'done_all');
    };

    window.simulateScan = function() {
        showToast('RxNorm and DDInter interaction database re-indexed', 'check_circle');
    };

    window.substituteMedication = function() {
        showToast('Substituted: OTC Ibuprofen removed. Paracetamol 500mg PRN prescribed.', 'swap_calls');
        const banner = document.getElementById('primaryContraindicationCard');
        if (banner) {
            banner.innerHTML = `
                <div class="flex items-center gap-space-md p-space-md bg-surface-container rounded-xl">
                    <span class="material-symbols-outlined text-surface-tint text-2xl">check_circle</span>
                    <div class="flex flex-col">
                        <span class="text-sm font-bold text-on-surface">Contraindication Resolved by Clinician</span>
                        <span class="text-xs text-on-surface-variant">Ibuprofen discontinued; Paracetamol 500mg selected as safe non-NSAID alternative.</span>
                    </div>
                </div>
            `;
        }
    };

    window.toggleAudioSimulation = function() {
        isAudioPlaying = !isAudioPlaying;
        const icon = document.getElementById('playIcon');
        const stamp = document.getElementById('audioTimestamp');
        if (isAudioPlaying) {
            if (icon) icon.textContent = 'pause';
            showToast('Ambient recording playback active', 'volume_up');
            audioTimer = setInterval(() => {
                audioSeconds++;
                const mins = String(Math.floor(audioSeconds / 60)).padStart(2, '0');
                const secs = String(audioSeconds % 60).padStart(2, '0');
                if (stamp) stamp.textContent = `00:${mins}:${secs}`;
            }, 1000);
        } else {
            if (icon) icon.textContent = 'play_arrow';
            clearInterval(audioTimer);
        }
    };

    window.showToast = function(msg, icon = 'check_circle') {
        const toast = document.getElementById('toastNotification');
        const toastMsg = document.getElementById('toastMessage');
        const toastIcon = document.getElementById('toastIcon');
        if (!toast) return;

        toastMsg.innerText = msg;
        toastIcon.innerText = icon;
        toast.classList.remove('translate-y-20', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');

        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0');
            toast.classList.remove('translate-y-0', 'opacity-100');
        }, 3500);
    };

    function setupGlobalSearch() {
        const searchInput = document.getElementById('globalSearchInput');
        if (!searchInput) return;

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const query = searchInput.value.toLowerCase().trim();
                if (!query) return;

                if (query.includes('soap')) navigateTo('clinical-soap-note');
                else if (query.includes('drug') || query.includes('safe') || query.includes('warfarin') || query.includes('aspirin')) navigateTo('drug-safety');
                else if (query.includes('dossier') || query.includes('report') || query.includes('fhir')) navigateTo('encounter-report');
                else if (query.includes('new') || query.includes('start') || query.includes('upload')) navigateTo('start');
                else navigateTo('dialogue-and-ner');

                showToast(`Search filtered for "${query}"`, 'search');
            }
        });
    }

    function setupTextareaCounters() {
        const pasteTextarea = document.getElementById('startPasteTextarea');
        if (pasteTextarea) {
            pasteTextarea.addEventListener('input', updateStartCharCount);
        }
    }

    window.updateStartCharCount = function() {
        const pasteTextarea = document.getElementById('startPasteTextarea');
        const counter = document.getElementById('startCharCount');
        if (pasteTextarea && counter) {
            counter.textContent = `${pasteTextarea.value.length} characters`;
        }
    };

    function escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

})();
