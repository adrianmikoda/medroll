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
        if (tabId === 'doctors') refreshDoctors();
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
        $('docCount').textContent = data.doctors_count;
        $('patCount').textContent = data.patients_count;

        $('dashInfo').innerHTML = [
            `  status .............. <span class="msg-ok">ONLINE</span>`,
            `  model_loaded ........ ${data.model_loaded ? '<span class="msg-ok">true</span>' : '<span class="msg-err">false</span>'}`,
            `  active_model ........ <span class="hl">${data.model_name} (${data.model_key})</span>`,
            `  doctors_registered .. <span class="hl">${data.doctors_count}</span>`,
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
        out += `  doctors loaded:  ${data.loaded_doctors.join(', ') || 'none'}\n`;
        out += `  patients loaded: ${data.loaded_patients.join(', ') || 'none'}`;
        setOutput('demoOutput', out);
        refreshDashboard();
    } catch (e) {
        setOutput('demoOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    } finally {
        btn.disabled = false;
    }
});

// ── Doctors ─────────────────────────────────────────────────
$('formAddDoctor').addEventListener('submit', async e => {
    e.preventDefault();
    setLoading('docAddOutput', 'Uploading & processing CV');

    const form = new FormData();
    form.append('file', $('docFile').files[0]);
    form.append('doctor_id', $('docId').value.trim());
    form.append('name', $('docName').value.trim());
    form.append('capacity', $('docCapacity').value);

    try {
        const data = await api('POST', '/api/doctors', form, true);
        setOutput('docAddOutput', `<span class="msg-ok">Doctor '${escHtml(data.doctor.doctor_id)}' added successfully.</span>`);
        $('formAddDoctor').reset();
        $('docCapacity').value = '5';
        refreshDoctors();
        refreshDashboard();
    } catch (e) {
        setOutput('docAddOutput', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
});

async function refreshDoctors() {
    try {
        const data = await api('GET', '/api/doctors');
        const docs = data.doctors;

        if (!docs.length) {
            setOutput('doctorsList', '<span class="dim">No doctors registered. Add a CV or load demo data.</span>');
            return;
        }

        let html = `<table class="cli-table">
<thead><tr>
    <th>ID</th><th>NAME</th><th>CAPACITY</th><th>LOAD</th><th>FILE</th><th>LANG</th><th></th>
</tr></thead><tbody>`;

        for (const d of docs) {
            html += `<tr>
    <td>${escHtml(d.doctor_id)}</td>
    <td>${escHtml(d.name)}</td>
    <td>${d.capacity}</td>
    <td>${d.current_load}</td>
    <td>${escHtml(d.filename)}</td>
    <td>${escHtml(d.language)}</td>
    <td><button class="cmd-btn cmd-btn-danger" onclick="deleteDoctor('${escHtml(d.doctor_id)}')">DEL</button></td>
</tr>`;
        }

        html += '</tbody></table>';
        setOutput('doctorsList', html);
    } catch (e) {
        setOutput('doctorsList', `<span class="msg-err">ERROR: ${escHtml(e.message)}</span>`);
    }
}

window.deleteDoctor = async function (id) {
    if (!confirm(`Delete doctor '${id}'?`)) return;
    try {
        await api('DELETE', `/api/doctors/${id}`);
        refreshDoctors();
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

        let html = `<table class="cli-table">
<thead><tr>
    <th>ID</th><th>FILE</th><th>LANG</th><th>CANDIDATES</th><th></th>
</tr></thead><tbody>`;

        for (const p of pats) {
            const candCount = (p.candidates || []).length;
            html += `<tr>
    <td>${escHtml(p.patient_id)}</td>
    <td>${escHtml(p.filename)}</td>
    <td>${escHtml(p.language)}</td>
    <td>${candCount > 0 ? `<span class="msg-ok">${candCount}</span>` : '<span class="dim">0</span>'}</td>
    <td><button class="cmd-btn cmd-btn-danger" onclick="deletePatient('${escHtml(p.patient_id)}')">DEL</button></td>
</tr>`;
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
        refreshDoctors();
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
                allHtml += `<div style="margin-bottom:12px">`;
                allHtml += `<span class="hl">── ${escHtml(p.patient_id)} ──</span>\n`;
                allHtml += renderSearchResultsHtml(data);
                allHtml += `</div>`;
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

    let html = `<table class="cli-table">
<thead><tr><th>#</th><th>DOCTOR_ID</th><th>FILE</th><th>DISTANCE</th><th>SCORE</th></tr></thead><tbody>`;

    data.results.forEach((r, i) => {
        html += `<tr>
    <td>${i + 1}</td>
    <td>${escHtml(r.doctor_id)}</td>
    <td>${escHtml(r.filename || '?')}</td>
    <td>${r.distance !== null ? r.distance.toFixed(4) : '?'}</td>
    <td>${scoreBar(r.score)}</td>
</tr>`;
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
        refreshDoctors();
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

    // Doctor loads
    html += `<div class="summary-block">
    <div class="summary-title">═══ DOCTOR LOADS ═══</div>`;
    for (const [docId, load] of Object.entries(data.doctor_loads)) {
        html += `<div class="summary-row"><span class="label">${escHtml(docId)}</span><span class="val">${load}</span></div>`;
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
        <span>doctor: <strong>${escHtml(d.assigned_doctor_id || '---')}</strong></span>
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
