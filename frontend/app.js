const API = '';

// ── Helpers ─────────────────────────────────────────────────
async function api(method, path, body, isForm = false) {
    const opts = { method };
    if (body) {
        if (isForm) {
            opts.body = body;
        } else {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(body);
        }
    }
    const res = await fetch(API + path, opts);
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || JSON.stringify(data));
    }
    return data;
}

function $(id) { return document.getElementById(id); }
function $$(sel) { return document.querySelectorAll(sel); }

function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function setOutput(elId, html, cls = '') {
    const el = $(elId);
    el.innerHTML = html;
    el.className = 'output-result' + (cls ? ' ' + cls : '');
}

function setLoading(elId, msg = 'Processing') {
    const el = $(elId);
    el.innerHTML = `<span class="loading">${escHtml(msg)} </span>`;
    el.className = 'output-result';
}

function scoreBar(score, maxWidth = 120) {
    const pct = Math.max(0, Math.min(1, score));
    const w = Math.round(pct * maxWidth);
    return `<span class="score-bar" style="width:${w}px"></span><span class="score-val">${score.toFixed(4)}</span>`;
}

// ── Tab routing ─────────────────────────────────────────────
function initTabs() {
    const navLinks = $$('.nav-cmd');

    function activateTab(tabId) {
        navLinks.forEach(l => l.classList.remove('active'));
        $$('.tab-content').forEach(t => t.classList.remove('active'));

        const link = document.querySelector(`[data-tab="${tabId}"]`);
        const tab = $(`tab-${tabId}`);

        if (link) link.classList.add('active');
        if (tab) tab.classList.add('active');

        // Refresh data on tab switch
        if (tabId === 'physicians') refreshPhysicians();
        if (tabId === 'patients') refreshPatients();
        if (tabId === 'assign') refreshSearchDropdown();
        if (tabId === 'config') refreshConfig();
        if (tabId === 'dashboard') refreshDashboard();
    }

    navLinks.forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const tab = link.dataset.tab;
            window.location.hash = tab;
            activateTab(tab);
        });
    });

    // Handle initial hash
    const hash = window.location.hash.slice(1) || 'dashboard';
    activateTab(hash);

    window.addEventListener('hashchange', () => {
        const h = window.location.hash.slice(1) || 'dashboard';
        activateTab(h);
    });
}

// ── Dashboard ───────────────────────────────────────────────
async function refreshDashboard() {
    try {
        const data = await api('GET', '/api/health');
        $('sysStatus').textContent = 'ONLINE';
        $('modelStatus').textContent = data.model_loaded ? `LOADED (${data.model_name})` : 'OFFLINE';
        $('modelStatus').style.color = data.model_loaded ? '' : '#ff4444';
        $('physCount').textContent = data.physicians_count;
        $('patCount').textContent = data.patients_count;

        $('dashInfo').innerHTML = [
            `  status .............. <span class="msg-ok">ONLINE</span>`,
            `  model_loaded ........ ${data.model_loaded ? '<span class="msg-ok">true</span>' : '<span class="msg-err">false</span>'}`,
            `  active_model ........ <span class="hl">${data.model_name} (${data.model_key})</span>`,
            `  physicians_registered .. <span class="hl">${data.physicians_count}</span>`,
            `  patients_registered . <span class="hl">${data.patients_count}</span>`,
            ``,
            data.model_loaded
                ? `  <span class="dim">Vector search ready. Upload documents or load demo data.</span>`
                : `  <span class="msg-warn">⚠ Model not loaded. You can still use demo data and manual assignment.</span>`,
        ].join('\n');
    } catch (e) {
        $('dashInfo').innerHTML = `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`;
        $('sysStatus').textContent = 'ERROR';
    }
}

// ── Load Demo ───────────────────────────────────────────────
$('btnLoadDemo').addEventListener('click', async () => {
    const btn = $('btnLoadDemo');
    btn.disabled = true;
    setLoading('demoOutput', 'Loading demo data');

    try {
        const data = await api('POST', '/api/demo/load');
        let out = `<span class="msg-ok">Demo data loaded successfully.</span>\n\n`;
        out += `  physicians loaded:  ${data.loaded_physicians.join(', ') || 'none'}\n`;
        out += `  patients loaded: ${data.loaded_patients.join(', ') || 'none'}`;
        setOutput('demoOutput', out);
        refreshDashboard();
    } catch (e) {
        setOutput('demoOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    } finally {
        btn.disabled = false;
    }
});

// ── Load Anonymized Demo ────────────────────────────────────
$('btnLoadAnonymizedDemo').addEventListener('click', async () => {
    const btn = $('btnLoadAnonymizedDemo');
    btn.disabled = true;
    setLoading('anonymizedDemoOutput', 'Loading anonymized demo data');

    try {
        const data = await api('POST', '/api/demo/load_anonymized');
        let out = `<span class="msg-ok">Anonymized demo data loaded successfully.</span>\n\n`;
        out += `  physicians loaded:  ${data.loaded_physicians.join(', ') || 'none'}\n`;
        out += `  patients loaded: ${data.loaded_patients.join(', ') || 'none'}`;
        setOutput('anonymizedDemoOutput', out);
        refreshDashboard();
    } catch (e) {
        setOutput('anonymizedDemoOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    } finally {
        btn.disabled = false;
    }
});


// ── Physicians ──────────────────────────────────────────────
$('formAddPhysician').addEventListener('submit', async e => {
    e.preventDefault();
    setLoading('physAddOutput', 'Uploading & processing CV');

    const form = new FormData();
    form.append('file', $('physFile').files[0]);
    form.append('physician_id', $('physId').value.trim());
    form.append('name', $('physName').value.trim());
    form.append('capacity', $('physCapacity').value);

    try {
        const data = await api('POST', '/api/physicians', form, true);
        setOutput('physAddOutput', `<span class="msg-ok">Physician '${escHtml(data.physician.physician_id)}' added successfully.</span>`);
        $('formAddPhysician').reset();
        $('physCapacity').value = '5';
        refreshPhysicians();
        refreshDashboard();
    } catch (e) {
        setOutput('physAddOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

async function refreshPhysicians() {
    try {
        const data = await api('GET', '/api/physicians');
        const physicians = data.physicians;

        if (!physicians.length) {
            setOutput('physiciansList', '<span class="dim">No physicians registered. Add a CV or load demo data.</span>');
            return;
        }

        let html = '<table class="cli-table"><thead><tr><th>ID</th><th>NAME</th><th>CAPACITY</th><th>LOAD</th><th>FILE</th><th>LANG</th><th></th></tr></thead><tbody>';

        for (const d of physicians) {
            html += `<tr><td>${escHtml(d.physician_id)}</td><td>${escHtml(d.name)}</td><td>${d.capacity}</td><td>${d.current_load}</td><td>${escHtml(d.filename)}</td><td>${escHtml(d.language)}</td><td><button class="cmd-btn cmd-btn-danger" onclick="deletePhysician('${escHtml(d.physician_id)}')">DEL</button></td></tr>`;
        }

        html += '</tbody></table>';
        setOutput('physiciansList', html);
    } catch (e) {
        setOutput('physiciansList', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
}

window.deletePhysician = async function (id) {
    if (!confirm(`Delete physician '${id}'?`)) return;
    try {
        await api('DELETE', `/api/physicians/${id}`);
        refreshPhysicians();
        refreshDashboard();
    } catch (e) {
        alert('Error: ' + e.message);
    }
};

// ── Patients ────────────────────────────────────────────────
$('formAddPatient').addEventListener('submit', async e => {
    e.preventDefault();
    setLoading('patAddOutput', 'Uploading & processing medical record');

    const form = new FormData();
    form.append('file', $('patFile').files[0]);
    form.append('patient_id', $('patId').value.trim());

    try {
        const data = await api('POST', '/api/patients', form, true);
        setOutput('patAddOutput', `<span class="msg-ok">Patient '${escHtml(data.patient.patient_id)}' added successfully.</span>`);
        $('formAddPatient').reset();
        refreshPatients();
        refreshDashboard();
    } catch (e) {
        setOutput('patAddOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

async function refreshPatients() {
    try {
        const data = await api('GET', '/api/patients');
        const pats = data.patients;

        if (!pats.length) {
            setOutput('patientsList', '<span class="dim">No patients registered. Upload a medical record or load demo data.</span>');
            return;
        }

        let html = '<table class="cli-table"><thead><tr><th>ID</th><th>FILE</th><th>LANG</th><th>CANDIDATES</th><th></th></tr></thead><tbody>';

        for (const p of pats) {
            const candCount = (p.candidates || []).length;
            const candHtml = candCount > 0 ? `<span class="msg-ok">${candCount}</span>` : '<span class="dim">0</span>';
            html += `<tr><td>${escHtml(p.patient_id)}</td><td>${escHtml(p.filename)}</td><td>${escHtml(p.language)}</td><td>${candHtml}</td><td><button class="cmd-btn cmd-btn-danger" onclick="deletePatient('${escHtml(p.patient_id)}')">DEL</button></td></tr>`;
        }

        html += '</tbody></table>';
        setOutput('patientsList', html);
    } catch (e) {
        setOutput('patientsList', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
}

window.deletePatient = async function (id) {
    if (!confirm(`Delete patient '${id}'?`)) return;
    try {
        await api('DELETE', `/api/patients/${id}`);
        refreshPatients();
        refreshPhysicians();
        refreshDashboard();
    } catch (e) {
        alert('Error: ' + e.message);
    }
};

// ── Search ──────────────────────────────────────────────────
async function refreshSearchDropdown() {
    try {
        const data = await api('GET', '/api/patients');
        const sel = $('searchPatientId');
        sel.innerHTML = '';

        if (!data.patients.length) {
            sel.innerHTML = '<option value="">-- no patients --</option>';
            return;
        }

        for (const p of data.patients) {
            const opt = document.createElement('option');
            opt.value = p.patient_id;
            opt.textContent = `${p.patient_id} (${p.filename})`;
            sel.appendChild(opt);
        }
    } catch (e) {
        // ignore
    }
}

$('btnSearch').addEventListener('click', async () => {
    const patientId = $('searchPatientId').value;
    const n = parseInt($('searchN').value) || 5;

    if (!patientId) {
        setOutput('searchOutput', '<span class="msg-warn">Select a patient first.</span>');
        return;
    }

    setLoading('searchOutput', `Searching vector DB for ${patientId}`);

    try {
        const data = await api('POST', '/api/search', { patient_id: patientId, n });
        renderSearchResults(data, 'searchOutput');
    } catch (e) {
        setOutput('searchOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

$('btnSearchAll').addEventListener('click', async () => {
    const n = parseInt($('searchN').value) || 5;
    setLoading('searchOutput', 'Searching for all patients');

    try {
        const patients = await api('GET', '/api/patients');
        let allHtml = '';

        for (const p of patients.patients) {
            try {
                const data = await api('POST', '/api/search', { patient_id: p.patient_id, n });
                allHtml += '<div style="margin-bottom:12px">';
                allHtml += `<span class="hl">── ${escHtml(p.patient_id)} ──</span><br>`;
                allHtml += renderSearchResultsHtml(data);
                allHtml += '</div>';
            } catch (e) {
                allHtml += `<span class="msg-err">${escHtml(p.patient_id)}: ${escHtml(e.message)}</span>\n`;
            }
        }

        setOutput('searchOutput', allHtml || '<span class="dim">No results.</span>');
    } catch (e) {
        setOutput('searchOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

function renderSearchResults(data, elId) {
    setOutput(elId, renderSearchResultsHtml(data));
}

function renderSearchResultsHtml(data) {
    if (!data.results || !data.results.length) {
        return '<span class="dim">No results found.</span>';
    }

    let html = '<table class="cli-table"><thead><tr><th>#</th><th>PHYSICIAN_ID</th><th>FILE</th><th>DISTANCE</th><th>SCORE</th></tr></thead><tbody>';

    data.results.forEach((r, i) => {
        const dist = r.distance !== null ? r.distance.toFixed(4) : '?';
        html += `<tr><td>${i + 1}</td><td>${escHtml(r.physician_id)}</td><td>${escHtml(r.filename || '?')}</td><td>${dist}</td><td>${scoreBar(r.score)}</td></tr>`;
    });

    html += '</tbody></table>';
    return html;
}

$('btnAssign').addEventListener('click', async () => {
    setLoading('assignOutput', 'Running Hungarian algorithm solver');

    try {
        const data = await api('POST', '/api/assign', {});
        renderAssignmentResults(data);
        setOutput('assignOutput', `<span class="msg-ok">Assignment complete. ${data.assigned_count} assigned, ${data.unassigned_count} unassigned.</span>`);
        refreshPhysicians();
        refreshDashboard();
    } catch (e) {
        setOutput('assignOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

function renderAssignmentResults(data) {
    let html = '';

    html += `<div class="summary-block">
    <div class="summary-title">═══ ASSIGNMENT SUMMARY ═══</div>
    <div class="summary-row"><span class="label">mode</span><span class="val">${data.mode}</span></div>
    <div class="summary-row"><span class="label">assigned</span><span class="val msg-ok">${data.assigned_count}</span></div>
    <div class="summary-row"><span class="label">unassigned</span><span class="val ${data.unassigned_count > 0 ? 'msg-err' : ''}">${data.unassigned_count}</span></div>
    <div class="summary-row"><span class="label">total_base_score</span><span class="val">${data.total_base_score}</span></div>
    <div class="summary-row"><span class="label">total_penalty</span><span class="val">${data.total_penalty}</span></div>
    <div class="summary-row"><span class="label">total_final_score</span><span class="val hl">${data.total_final_score}</span></div>
</div>`;

    // Physician loads
    html += `<div class="summary-block">
    <div class="summary-title">═══ PHYSICIAN LOADS ═══</div>`;
    for (const [physId, load] of Object.entries(data.physician_loads)) {
        html += `<div class="summary-row"><span class="label">${escHtml(physId)}</span><span class="val">${load}</span></div>`;
    }
    html += '</div>';

    // Decisions
    html += `<div class="summary-title" style="margin-bottom:8px">═══ DECISIONS ═══</div>`;

    for (const d of data.decisions) {
        const isAssigned = d.reason === 'assigned';
        html += `<div class="decision-card ${isAssigned ? 'assigned' : 'unassigned'}">
    <div class="decision-header">
        <span class="decision-patient">${escHtml(d.patient_id)}</span>
        <span class="decision-status ${isAssigned ? 'ok' : 'fail'}">${isAssigned ? '✓ ASSIGNED' : '✗ UNASSIGNED'}</span>
    </div>
    <div class="decision-details">
        <span>physician: <strong>${escHtml(d.assigned_physician_id || '---')}</strong></span>
        <span>slot: ${d.assigned_slot_index ?? '---'}</span>
        <span>rank: ${d.candidate_rank ?? '---'}</span>
        <span>base: ${d.base_score}</span>
        <span>penalty: ${d.slot_penalty}</span>
        <span>final: <span class="hl">${d.final_score}</span></span>
    </div>
</div>`;
    }

    setOutput('assignResults', html);
}

// ── Config ──────────────────────────────────────────────────
async function refreshConfig() {
    try {
        const data = await api('GET', '/api/config');

        const modelSel = $('cfgModel');
        if (modelSel) {
            modelSel.innerHTML = '';
            (data.models || []).forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === data.model_key) {
                    opt.selected = true;
                }
                modelSel.appendChild(opt);
            });
        }

        const modeSel = $('cfgMode');
        if (modeSel) {
            modeSel.innerHTML = '';
            (data.modes || []).forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                if (m === data.mode) {
                    opt.selected = true;
                }
                modeSel.appendChild(opt);
            });
        }

        $('cfgWeight').value = data.load_penalty_weight;
        $('cfgExponent').value = data.load_penalty_exponent;
        $('cfgUnassigned').value = data.unassigned_score;
        $('cfgMinScore').value = data.min_candidate_score;

        let html = '';
        for (const [k, v] of Object.entries(data)) {
            if (k === 'models' || k === 'modes') continue;
            html += `  ${k.padEnd(25)} = <span class="hl">${v}</span>\n`;
        }
        setOutput('configCurrent', html);
    } catch (e) {
        setOutput('configCurrent', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
}

$('formConfig').addEventListener('submit', async e => {
    e.preventDefault();
    setLoading('configOutput', 'Updating config');

    try {
        const payload = {
            load_penalty_weight: parseFloat($('cfgWeight').value),
            load_penalty_exponent: parseFloat($('cfgExponent').value),
            unassigned_score: parseFloat($('cfgUnassigned').value),
            min_candidate_score: parseFloat($('cfgMinScore').value),
        };
        const modelSel = $('cfgModel');
        if (modelSel) {
            payload.model_key = modelSel.value;
        }
        const modeSel = $('cfgMode');
        if (modeSel) {
            payload.mode = modeSel.value;
        }
        const data = await api('PUT', '/api/config', payload);
        setOutput('configOutput', `<span class="msg-ok">Config updated successfully.</span>`);
        refreshConfig();
        refreshDashboard();
    } catch (e) {
        setOutput('configOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    refreshDashboard();
});
