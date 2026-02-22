"""
thermal_dashboard.py

ResQ – Thermal Camera Test Dashboard
Full cyberpunk-styled page embedded in the same backend.
Accessible via /dashboard/thermal with a switch button from main dashboard.
"""


def get_thermal_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ResQ | Thermal Vision Lab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">

<style>
:root {
    --bg:        #030a0a;
    --card-bg:   rgba(0, 30, 30, 0.65);
    --heat-1:    #ff4500;   /* HIGH  – thermal red   */
    --heat-2:    #ff9900;   /* MED   – thermal amber */
    --heat-3:    #00e5ff;   /* LOW   – cool cyan     */
    --accent:    #ff6a00;
    --border:    rgba(255, 106, 0, 0.25);
    --text:      #f1f5f9;
    --sub:       rgba(255,255,255,0.4);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

/* ── HEADER ─────────────────────────────────── */
header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 32px;
    background: rgba(0,0,0,0.8);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(10px);
}

.header-left { display: flex; align-items: center; gap: 14px; }

.logo-icon {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: radial-gradient(circle, #ff4500 0%, #ff6a00 60%, transparent 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    box-shadow: 0 0 16px #ff450066;
    animation: pulseglow 2s ease-in-out infinite;
}

@keyframes pulseglow {
    0%,100% { box-shadow: 0 0 12px #ff450066; }
    50%      { box-shadow: 0 0 28px #ff4500bb; }
}

.header-title { font-size: 18px; color: var(--accent); letter-spacing: 3px; }
.header-sub   { font-size: 10px; color: var(--sub); letter-spacing: 2px; margin-top: 2px; }

.switch-btn {
    padding: 10px 22px;
    border-radius: 8px;
    border: 1px solid rgba(34,211,238,0.4);
    background: rgba(34,211,238,0.08);
    color: #22d3ee;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 2px;
    cursor: pointer;
    text-decoration: none;
    transition: all .2s;
}
.switch-btn:hover { background: rgba(34,211,238,0.18); border-color: #22d3ee; }

/* ── MAIN LAYOUT ─────────────────────────────── */
.main {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 18px;
    padding: 18px;
    overflow: hidden;
}

/* ── LEFT COLUMN ─────────────────────────────── */
.left-col { display: flex; flex-direction: column; gap: 14px; overflow: hidden; }

/* Upload Zone */
.upload-zone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    background: var(--card-bg);
    padding: 28px 20px;
    text-align: center;
    cursor: pointer;
    transition: border-color .25s, background .25s;
    position: relative;
}
.upload-zone.drag-over {
    border-color: var(--accent);
    background: rgba(255,106,0,0.08);
}
.upload-zone input { display: none; }
.upload-zone .icon { font-size: 40px; margin-bottom: 8px; }
.upload-zone .hint { font-size: 12px; color: var(--sub); margin-top: 6px; letter-spacing: 1px; }
.upload-zone .btn-row { display: flex; gap: 10px; justify-content: center; margin-top: 14px; flex-wrap: wrap; }

/* Mode chips */
.mode-chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.chip {
    padding: 6px 18px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: rgba(255,106,0,0.06);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all .2s;
}
.chip:hover   { border-color: var(--accent); color: var(--accent); }
.chip.active  { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 700; }

.action-btn {
    padding: 12px 28px;
    border-radius: 8px;
    border: none;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    cursor: pointer;
    transition: all .2s;
}
.btn-detect  { background: var(--accent); color: #000; }
.btn-detect:hover { background: #ff8c00; }
.btn-detect:disabled { background: rgba(255,106,0,0.3); cursor: not-allowed; color: rgba(0,0,0,0.4); }
.btn-clear   { background: transparent; border: 1px solid var(--border); color: var(--sub); }
.btn-clear:hover { border-color: var(--accent); color: var(--accent); }

/* Image Preview Area */
.preview-area {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    min-height: 0;
}

.img-panel {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.img-panel-header {
    padding: 10px 14px;
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--sub);
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.img-panel-header .badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 9px;
}
.badge-original  { background: rgba(255,255,255,0.08); color: var(--sub); }
.badge-processed { background: rgba(255,106,0,0.2);    color: var(--accent); }

.img-panel img {
    width: 100%; height: 100%;
    object-fit: contain;
    background: #000;
    display: block;
}

.img-placeholder {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255,255,255,0.1);
    font-size: 40px;
    background: repeating-linear-gradient(
        45deg,
        transparent, transparent 10px,
        rgba(255,106,0,0.02) 10px,
        rgba(255,106,0,0.02) 20px
    );
}

/* ── RIGHT COLUMN ─────────────────────────────── */
.right-col {
    display: flex;
    flex-direction: column;
    gap: 14px;
    overflow-y: auto;
    padding-right: 4px;
}

.section-label {
    font-size: 10px;
    letter-spacing: 3px;
    color: var(--accent);
    opacity: 0.7;
    margin-bottom: 4px;
}

/* Status bar */
.status-bar {
    padding: 12px 16px;
    border-radius: 8px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    font-size: 12px;
    letter-spacing: 1px;
    transition: all .3s;
    min-height: 44px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--sub);
}
.status-dot.idle    { background: rgba(255,255,255,0.2); }
.status-dot.working { background: var(--accent); animation: blink .7s ease-in-out infinite; }
.status-dot.done    { background: #22c55e; }
.status-dot.error   { background: #f43f5e; }

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }

/* Stats row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
}
.stat-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 8px;
    text-align: center;
}
.stat-value { font-size: 22px; font-weight: 700; }
.stat-label { font-size: 9px; color: var(--sub); letter-spacing: 1px; margin-top: 2px; }
.high-val   { color: var(--heat-1); }
.med-val    { color: var(--heat-2); }
.low-val    { color: var(--heat-3); }

/* Victim cards */
.victim-scroll { display: flex; flex-direction: column; gap: 8px; }

.victim-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-left: 4px solid transparent;
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 12px;
    animation: fadein .3s ease;
}
@keyframes fadein { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }
.victim-card.HIGH   { border-left-color: var(--heat-1); }
.victim-card.MEDIUM { border-left-color: var(--heat-2); }
.victim-card.LOW    { border-left-color: var(--heat-3); }

.victim-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.victim-id     { font-weight: 700; font-size: 14px; }
.priority-badge {
    padding: 2px 10px; border-radius: 4px; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
.p-HIGH   { background: rgba(255,69,0,0.2);  color: var(--heat-1); border: 1px solid var(--heat-1); }
.p-MEDIUM { background: rgba(255,153,0,0.2); color: var(--heat-2); border: 1px solid var(--heat-2); }
.p-LOW    { background: rgba(0,229,255,0.1); color: var(--heat-3); border: 1px solid var(--heat-3); }

.victim-meta { font-size: 10px; color: var(--sub); line-height: 1.8; }

/* Empty state */
.empty-state {
    text-align: center;
    padding: 30px 0;
    color: rgba(255,255,255,0.12);
    font-size: 13px;
    letter-spacing: 2px;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
</style>
</head>
<body>

<!-- HEADER -->
<header>
  <div class="header-left">
    <div class="logo-icon">🌡️</div>
    <div>
      <div class="header-title">THERMAL_VISION_LAB</div>
      <div class="header-sub">INFRARED DETECTION · RESQ SYSTEM</div>
    </div>
  </div>
  <a href="/dashboard" class="switch-btn">⬅ RGB COMMAND CENTER</a>
</header>

<!-- MAIN -->
<div class="main">

  <!-- LEFT: Upload + Preview -->
  <div class="left-col">

    <!-- Upload Zone -->
    <div class="upload-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
      <input type="file" id="fileInput" accept="image/*" onchange="onFileSelect(event)">
      <div class="icon">🔥</div>
      <div style="font-size:14px;letter-spacing:2px;">DROP THERMAL IMAGE HERE</div>
      <div class="hint">SUPPORTS JPG · PNG · BMP · TIFF</div>

      <div style="margin-top:14px;font-size:10px;color:rgba(255,106,0,0.7);letter-spacing:2px;">
        PREPROCESSING MODE
      </div>
      <div class="mode-chips" id="modeChips" style="margin-top:8px;" onclick="event.stopPropagation()">
        <button class="chip active" onclick="setMode('clahe', this)">⚡ CLAHE</button>
        <button class="chip"       onclick="setMode('false_color', this)">🌈 FALSE COLOR</button>
        <button class="chip"       onclick="setMode('raw', this)">📷 RAW</button>
      </div>

      <div class="btn-row" onclick="event.stopPropagation()">
        <button class="action-btn btn-detect" id="detectBtn" onclick="runDetect()" disabled>
          🔍 DETECT PERSONS
        </button>
        <button class="action-btn btn-clear" onclick="clearAll()">✖ CLEAR</button>
      </div>
    </div>

    <!-- Image Previews -->
    <div class="preview-area">
      <div class="img-panel">
        <div class="img-panel-header">
          ORIGINAL INPUT
          <span class="badge badge-original" id="modeLabel">—</span>
        </div>
        <div class="img-placeholder" id="origPlaceholder">📷</div>
        <img id="origImg" style="display:none; flex:1;" alt="original">
      </div>

      <div class="img-panel">
        <div class="img-panel-header">
          ANNOTATED RESULT
          <span class="badge badge-processed" id="procLabel">AWAITING</span>
        </div>
        <div class="img-placeholder" id="annPlaceholder">🎯</div>
        <img id="annImg" style="display:none; flex:1;" src="" alt="annotated"
             onerror="this.style.display='none'; document.getElementById('annPlaceholder').style.display='flex'">
      </div>
    </div>

  </div>

  <!-- RIGHT: Status + Results -->
  <div class="right-col">

    <!-- Status -->
    <div>
      <div class="section-label">SYSTEM STATUS</div>
      <div class="status-bar" id="statusBar">
        <div class="status-dot idle" id="statusDot"></div>
        <span id="statusText">AWAITING THERMAL INPUT</span>
      </div>
    </div>

    <!-- Stats -->
    <div>
      <div class="section-label">DETECTION SUMMARY</div>
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-value" id="totalCount" style="color:var(--accent)">—</div>
          <div class="stat-label">DETECTED</div>
        </div>
        <div class="stat-card">
          <div class="stat-value high-val" id="highCount">—</div>
          <div class="stat-label">HIGH</div>
        </div>
        <div class="stat-card">
          <div class="stat-value med-val" id="medCount">—</div>
          <div class="stat-label">MEDIUM</div>
        </div>
      </div>
    </div>

    <!-- Victims -->
    <div>
      <div class="section-label">DETECTED TARGETS</div>
      <div class="victim-scroll" id="victimList">
        <div class="empty-state">NO SCAN DATA</div>
      </div>
    </div>

  </div>
</div>

<script>
let selectedFile = null;
let currentMode  = 'clahe';

// ── FILE SELECTION ─────────────────────────
function onFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    loadFile(file);
}

function loadFile(file) {
    selectedFile = file;
    const url = URL.createObjectURL(file);
    document.getElementById('origImg').src = url;
    document.getElementById('origImg').style.display = 'block';
    document.getElementById('origPlaceholder').style.display = 'none';
    document.getElementById('modeLabel').innerText = currentMode.toUpperCase();
    document.getElementById('detectBtn').disabled = false;
    setStatus('idle', 'IMAGE LOADED · READY TO DETECT');
}

// ── DRAG & DROP ────────────────────────────
const dropZone = document.getElementById('dropZone');

dropZone.addEventListener('dragover', e => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) loadFile(file);
});

// ── MODE CHIPS ─────────────────────────────
function setMode(mode, el) {
    currentMode = mode;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    if (el) el.classList.add('active');
    document.getElementById('modeLabel').innerText = mode.toUpperCase();
}

// ── STATUS ─────────────────────────────────
function setStatus(state, msg) {
    document.getElementById('statusDot').className = 'status-dot ' + state;
    document.getElementById('statusText').innerText = msg;
}

// ── DETECT ─────────────────────────────────
async function runDetect() {
    if (!selectedFile) return;

    const btn = document.getElementById('detectBtn');
    btn.disabled = true;
    setStatus('working', 'PROCESSING THERMAL IMAGE...');

    const fd = new FormData();
    fd.append('file', selectedFile);

    try {
        const res = await fetch('/detect-thermal?mode=' + currentMode, {
            method: 'POST',
            body: fd
        });

        if (!res.ok) throw new Error('Server returned ' + res.status);

        const data = await res.json();
        renderResults(data);

        // Refresh annotated image (cache-bust)
        const ann = document.getElementById('annImg');
        ann.src = '/static/thermal_annotated.jpg?t=' + Date.now();
        ann.style.display = 'block';
        document.getElementById('annPlaceholder').style.display = 'none';
        document.getElementById('procLabel').innerText = 'PROCESSED ✔';

        setStatus('done', 'DETECTION COMPLETE · ' + data.count + ' PERSON(S) FOUND');

    } catch(err) {
        setStatus('error', 'ERROR: ' + err.message);
    } finally {
        btn.disabled = false;
    }
}

// ── RENDER RESULTS ─────────────────────────
function renderResults(data) {
    // Stats
    const victims  = data.victims || [];
    const high     = victims.filter(v => v.priority === 'HIGH').length;
    const med      = victims.filter(v => v.priority === 'MEDIUM').length;

    document.getElementById('totalCount').innerText = data.count;
    document.getElementById('highCount').innerText  = high;
    document.getElementById('medCount').innerText   = med;

    // Victim cards
    const list = document.getElementById('victimList');
    list.innerHTML = '';

    if (victims.length === 0) {
        list.innerHTML = '<div class="empty-state">NO PERSONS DETECTED</div>';
        return;
    }

    victims.sort((a,b) => {
        const o = {HIGH:0,MEDIUM:1,LOW:2};
        return (o[a.priority]||3) - (o[b.priority]||3);
    });

    victims.forEach(v => {
        const card = document.createElement('div');
        card.className = 'victim-card ' + v.priority;
        card.innerHTML = `
            <div class="victim-header">
                <span class="victim-id">TARGET_${v.id.toString().padStart(2,'0')}</span>
                <span class="priority-badge p-${v.priority}">${v.priority}</span>
            </div>
            <div class="victim-meta">
                POSE     : ${(v.pose || 'unknown').toUpperCase()}<br>
                GRID     : [${v.grid || '?'}]<br>
                CONF     : ${((v.confidence||0)*100).toFixed(1)}%<br>
                RISK     : ${v.risk_score !== undefined ? v.risk_score : '—'}<br>
                MODE     : ${data.preprocessing_mode || currentMode}
            </div>
        `;
        list.appendChild(card);
    });
}

// ── CLEAR ──────────────────────────────────
function clearAll() {
    selectedFile = null;
    document.getElementById('origImg').style.display = 'none';
    document.getElementById('origPlaceholder').style.display = 'flex';
    document.getElementById('annImg').style.display = 'none';
    document.getElementById('annPlaceholder').style.display = 'flex';
    document.getElementById('modeLabel').innerText = '—';
    document.getElementById('procLabel').innerText = 'AWAITING';
    document.getElementById('detectBtn').disabled = true;
    document.getElementById('totalCount').innerText = '—';
    document.getElementById('highCount').innerText  = '—';
    document.getElementById('medCount').innerText   = '—';
    document.getElementById('victimList').innerHTML = '<div class="empty-state">NO SCAN DATA</div>';
    document.getElementById('fileInput').value = '';
    setStatus('idle', 'AWAITING THERMAL INPUT');
}
</script>

</body>
</html>"""
