"""
dashboard.py

ResQ – Main RGB Command Dashboard v2
New features:
  - WebSocket live updates (no more 2s polling)
  - Audio alarm on HIGH priority detection
  - Multi-drone selector
  - Mission history log panel
  - Export report (JSON download)
  - 🌡️ THERMAL LAB and 🎥 VIDEO LAB switch buttons
"""


def get_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ResQ | Command Center</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">

<style>
:root {
    --bg:       #05070a;
    --card-bg:  rgba(15,23,42,0.6);
    --cyan:     #22d3ee;
    --red:      #f43f5e;
    --yellow:   #fbbf24;
    --green:    #10b981;
    --orange:   #ff6a00;
    --border:   rgba(34,211,238,0.2);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg);
    color: #f8fafc;
    font-family: 'JetBrains Mono', monospace;
    display: flex; flex-direction: column; height: 100vh;
    overflow: hidden;
}

/* ── HEADER ──────────────────────────────── */
header {
    padding: 14px 28px;
    background: rgba(2,6,23,0.95);
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    flex-shrink: 0;
}
.title { font-size: 18px; color: var(--cyan); letter-spacing: 2px; }
.header-right { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sysTime { font-size: 11px; opacity: 0.4; }
.ws-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #f43f5e; transition: background .3s;
}
.ws-dot.connected { background: var(--green); }

.nav-btn {
    padding: 7px 16px; border-radius: 6px; font-family: inherit;
    font-size: 10px; letter-spacing: 2px; cursor: pointer; text-decoration: none;
    border: 1px solid; transition: all .2s;
}
.nav-btn-thermal {
    border-color: rgba(255,106,0,0.4); background: rgba(255,106,0,0.08); color: #ff6a00;
}
.nav-btn-thermal:hover { background: rgba(255,106,0,0.2); }
.nav-btn-video {
    border-color: var(--border); background: rgba(34,211,238,0.06); color: var(--cyan);
}
.nav-btn-video:hover { background: rgba(34,211,238,0.15); }
.export-btn {
    padding: 7px 16px; border-radius: 6px; font-family: inherit; font-size: 10px;
    letter-spacing: 2px; cursor: pointer; border: 1px solid rgba(16,185,129,0.4);
    background: rgba(16,185,129,0.08); color: var(--green);
}
.export-btn:hover { background: rgba(16,185,129,0.18); }

/* ── DRONE SELECTOR ──────────────────────── */
.drone-bar {
    padding: 8px 28px;
    background: rgba(2,6,23,0.8);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 10px;
    flex-shrink: 0;
}
.drone-bar-label { font-size: 10px; color: rgba(255,255,255,0.3); letter-spacing: 2px; margin-right: 6px; }
.drone-chip {
    padding: 4px 14px; border-radius: 12px; font-size: 10px; letter-spacing: 1px;
    border: 1px solid var(--border); background: rgba(34,211,238,0.05);
    color: rgba(255,255,255,0.5); cursor: pointer; font-family: inherit;
}
.drone-chip.active { background: var(--cyan); color: #000; border-color: var(--cyan); font-weight: 700; }
.drone-chip:hover:not(.active) { border-color: var(--cyan); color: var(--cyan); }
#allDronesBtn.active { background: rgba(255,255,255,0.15); color: #fff; border-color: rgba(255,255,255,0.3); }

/* ── MAIN GRID ───────────────────────────── */
.main {
    flex: 1; display: grid; grid-template-columns: 2.6fr 1fr;
    gap: 16px; padding: 16px; overflow: hidden;
}

/* ── FEED ────────────────────────────────── */
.feed-container {
    position: relative; background: var(--card-bg);
    border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
    display: flex; flex-direction: column;
}
.feed-container img { width: 100%; height: 100%; object-fit: contain; background: #000; min-height: 0; }
.feed-label {
    padding: 8px 14px; font-size: 10px; color: rgba(255,255,255,0.3);
    letter-spacing: 2px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
}

/* ── SIDEBAR ─────────────────────────────── */
.sidebar {
    display: flex; flex-direction: column; gap: 12px; overflow: hidden;
}

.section-title {
    font-size: 10px; color: var(--cyan); letter-spacing: 3px; opacity: 0.7;
    margin-bottom: 4px;
}

/* Victim cards */
.victim-scroll { overflow-y: auto; display: flex; flex-direction: column; gap: 6px; max-height: 260px; }
.card {
    background: var(--card-bg); border: 1px solid var(--border);
    border-left: 4px solid transparent; border-radius: 8px; padding: 10px 12px; font-size: 12px;
    animation: fadein .25s ease;
}
@keyframes fadein { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
.card.HIGH   { border-left-color: var(--red); }
.card.MEDIUM { border-left-color: var(--yellow); }
.card.LOW    { border-left-color: var(--green); }

/* Tactical grid */
.map-container {
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px; display: flex; justify-content: center; flex-shrink: 0;
}
.map-grid {
    display: grid; grid-template-columns: repeat(10,1fr);
    grid-template-rows: repeat(10,1fr); gap: 2px; width: 200px; height: 200px;
}
.cell { background: rgba(0,0,0,0.35); border: 1px solid rgba(34,211,238,0.1); position: relative; }
.dot {
    width: 9px; height: 9px; border-radius: 50%; position: absolute;
    top:50%; left:50%; transform:translate(-50%,-50%);
}

/* History log */
.history-panel {
    flex: 1; background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 10px; overflow: hidden; min-height: 0; display: flex; flex-direction: column;
}
.history-scroll { overflow-y: auto; flex: 1; padding: 6px; }
.log-row {
    font-size: 9px; padding: 4px 6px; border-bottom: 1px solid rgba(255,255,255,0.04);
    display: flex; gap: 8px; align-items: center;
}
.log-row:last-child { border-bottom: none; }
.log-p { padding: 1px 6px; border-radius: 3px; font-size: 8px; font-weight:700; flex-shrink:0; }
.log-p.HIGH   { background: rgba(244,63,94,0.2);  color: var(--red); }
.log-p.MEDIUM { background: rgba(251,191,36,0.2); color: var(--yellow); }
.log-p.LOW    { background: rgba(16,185,129,0.2); color: var(--green); }
.log-time { opacity: 0.35; flex-shrink: 0; }

/* Footer decision bar */
.footer {
    min-height: 52px; background: rgba(2,6,23,0.95);
    border-top: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; letter-spacing: 2px; flex-shrink: 0; padding: 0 20px;
}

/* Scrollbar */
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>

<!-- HEADER -->
<header>
  <div class="title">RESQ_COMMAND_CENTER_V2</div>
  <div class="header-right">
    <div style="display:flex;align-items:center;gap:6px;">
      <div class="ws-dot" id="wsDot"></div>
      <span style="font-size:9px;opacity:.4;" id="wsLabel">CONNECTING</span>
    </div>
    <div class="sysTime" id="sysTime">--:--:--</div>
    <button class="export-btn" onclick="exportReport()">⬇ EXPORT</button>
    <a href="/dashboard/thermal" class="nav-btn nav-btn-thermal">🌡️ THERMAL</a>
    <a href="/dashboard/video"   class="nav-btn nav-btn-video">🎥 VIDEO</a>
  </div>
</header>

<!-- DRONE SELECTOR -->
<div class="drone-bar" id="droneBar">
  <span class="drone-bar-label">DRONE ▸</span>
  <button class="drone-chip active" id="allDronesBtn" onclick="selectDrone(null, this)">ALL</button>
</div>

<!-- MAIN -->
<div class="main">
  <!-- LEFT: Feed -->
  <div class="feed-container">
    <div class="feed-label">
      <span>LIVE FEED</span>
      <span id="feedDroneLabel" style="color:var(--cyan);">ALL DRONES</span>
    </div>
    <img id="feed" src="/static/latest_annotated.jpg" alt="feed">
  </div>

  <!-- RIGHT: Sidebar -->
  <div class="sidebar">
    <div>
      <div class="section-title">TARGETS</div>
      <div class="victim-scroll" id="victimList"><div style="opacity:.3;font-size:11px;">NO DATA</div></div>
    </div>
    <div>
      <div class="section-title">TACTICAL GRID</div>
      <div class="map-container"><div id="map" class="map-grid"></div></div>
    </div>
    <div class="history-panel">
      <div style="padding:8px 10px;border-bottom:1px solid var(--border);font-size:10px;color:var(--cyan);letter-spacing:2px;opacity:.7;">
        MISSION LOG
      </div>
      <div class="history-scroll" id="historyLog"><div style="opacity:.3;font-size:10px;padding:8px;">LOADING...</div></div>
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="footer" id="decision">STANDBY: AWAITING DATA</div>

<script>
// ── AUDIO ALERT ──────────────────────────────────────
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;
let lastHighAlert = 0;

function playAlarm() {
    const now = Date.now();
    if (now - lastHighAlert < 8000) return; // max every 8s
    lastHighAlert = now;
    try {
        if (!audioCtx) audioCtx = new AudioCtx();
        [600, 800, 600].forEach((freq, i) => {
            const osc  = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.frequency.value = freq;
            osc.type = "square";
            gain.gain.setValueAtTime(0.15, audioCtx.currentTime + i * 0.18);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + i * 0.18 + 0.15);
            osc.start(audioCtx.currentTime + i * 0.18);
            osc.stop(audioCtx.currentTime + i * 0.18 + 0.18);
        });
    } catch(e) {}
}

// ── STATE ────────────────────────────────────────────
let currentDrone = null; // null = all
let allVictims   = [];
let knownDrones  = new Set();

// ── SYSTEM CLOCK ─────────────────────────────────────
setInterval(() => {
    const n = new Date();
    document.getElementById("sysTime").innerText =
        "SYSTEM_TIME: " + n.toTimeString().slice(0, 8);
}, 1000);

// ── DRONE SELECTOR ───────────────────────────────────
function selectDrone(droneId, el) {
    currentDrone = droneId;
    document.querySelectorAll(".drone-chip").forEach(c => c.classList.remove("active"));
    el.classList.add("active");
    document.getElementById("feedDroneLabel").innerText =
        droneId ? droneId : "ALL DRONES";
    renderVictims(allVictims);
}

function updateDroneChips(drones) {
    const bar = document.getElementById("droneBar");
    drones.forEach(id => {
        if (knownDrones.has(id)) return;
        knownDrones.add(id);
        const btn = document.createElement("button");
        btn.className = "drone-chip";
        btn.innerText = id;
        btn.onclick = () => selectDrone(id, btn);
        bar.appendChild(btn);
    });
}

// ── WEBSOCKET ────────────────────────────────────────
let ws;
function connectWS() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws");

    ws.onopen = () => {
        document.getElementById("wsDot").className   = "ws-dot connected";
        document.getElementById("wsLabel").innerText = "LIVE";
        // Keep-alive ping every 25s
        setInterval(() => { if (ws.readyState === 1) ws.send("ping"); }, 25000);
    };

    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        allVictims = data.victims || [];
        updateDroneChips(data.drones || []);
        renderVictims(allVictims);
        refreshFeed();
    };

    ws.onclose = () => {
        document.getElementById("wsDot").className   = "ws-dot";
        document.getElementById("wsLabel").innerText = "RECONNECTING";
        setTimeout(connectWS, 3000); // auto-reconnect
    };
    ws.onerror = () => ws.close();
}
connectWS();

// ── FEED REFRESH ─────────────────────────────────────
function refreshFeed() {
    document.getElementById("feed").src =
        "/static/latest_annotated.jpg?t=" + Date.now();
}
setInterval(refreshFeed, 3000); // fallback refresh

// ── RENDER VICTIMS ───────────────────────────────────
const ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 };

function renderVictims(victims) {
    const filtered = currentDrone
        ? victims.filter(v => v.drone_id === currentDrone)
        : victims;

    // Tactical grid
    if (!document.getElementById("map").children.length) {
        for (let i = 0; i < 100; i++) {
            const c = document.createElement("div");
            c.className = "cell";
            document.getElementById("map").appendChild(c);
        }
    }
    [...document.getElementById("map").children].forEach(c => c.innerHTML = "");

    const list = document.getElementById("victimList");
    list.innerHTML = "";

    if (!filtered.length) {
        list.innerHTML = '<div style="opacity:.3;font-size:11px;letter-spacing:1px;">AREA CLEAR</div>';
        document.getElementById("decision").innerText = "AREA_CLEAR: NO RESCUE REQUIRED";
        document.getElementById("decision").style.color = "var(--green)";
        return;
    }

    const sorted = [...filtered].sort((a, b) =>
        (!a.rescued - !b.rescued) || (ORDER[a.priority] || 3) - (ORDER[b.priority] || 3)
    );

    let hasHigh = false;

    sorted.forEach(v => {
        if (v.priority === "HIGH" && !v.rescued) hasHigh = true;

        // Card
        const card = document.createElement("div");
        card.className = "card " + v.priority;
        let statusHTML = v.rescued
            ? `<div style="color:var(--green);margin-top:4px;font-size:10px;">✔ RESCUED</div>`
            : v.onway
            ? `<div style="color:var(--yellow);margin-top:4px;font-size:10px;">🚑 ${v.rescuer || "RESPONDER"} ON THE WAY</div>`
            : `<div style="color:var(--red);margin-top:4px;font-size:10px;">❗ AWAITING</div>`;

        const droneTag = v.drone_id ? `<span style="opacity:.4;font-size:9px;"> [${v.drone_id}]</span>` : "";
        card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong>ID_${v.id}${droneTag}</strong>
                <span style="font-size:10px;opacity:.5;">${v.priority}</span>
            </div>
            <div style="font-size:10px;opacity:.5;margin-top:2px;">${v.pose} · Grid ${v.grid}</div>
            ${statusHTML}
        `;
        list.appendChild(card);

        // Map dot
        if (v.grid && v.grid.length >= 2) {
            const idx = v.grid[0] * 10 + v.grid[1];  // 0-indexed, 10 cols
            const cell = document.getElementById("map").children[idx];
            if (cell) {
                const color = v.priority === "HIGH" ? "var(--red)" :
                              v.priority === "MEDIUM" ? "var(--yellow)" : "var(--green)";
                cell.innerHTML = `<div class="dot" style="background:${color}"></div>`;
            }
        }
    });

    if (hasHigh) playAlarm();

    // Footer decision
    const active = sorted.filter(v => !v.rescued);
    const dec    = document.getElementById("decision");
    if (active.length) {
        const top = active[0];
        dec.innerHTML = `<span style="color:var(--red);font-weight:700;">CRITICAL ACTION:</span>&nbsp;
            DEPLOY TO ID_${top.id} [GRID ${top.grid}]${top.drone_id ? " [" + top.drone_id + "]" : ""}`;
    } else {
        dec.innerHTML = `<span style="color:var(--green);font-weight:700;">ALL TARGETS SECURED</span>`;
    }
}

// ── HISTORY LOG ──────────────────────────────────────
async function loadHistory() {
    try {
        const res  = await fetch("/history?limit=40");
        const data = await res.json();
        const log  = document.getElementById("historyLog");
        if (!data.events || !data.events.length) {
            log.innerHTML = '<div style="opacity:.3;font-size:10px;padding:8px;">NO EVENTS YET</div>';
            return;
        }
        log.innerHTML = data.events.map(e => {
            const t = e.detected_at ? e.detected_at.slice(11, 19) : "--:--:--";
            return `<div class="log-row">
                <span class="log-p ${e.priority}">${e.priority[0]}</span>
                <span style="opacity:.7;flex:1;">ID_${e.victim_id} ${e.pose || ""} [${e.drone_id}]</span>
                <span class="log-time">${t}</span>
            </div>`;
        }).join("");
    } catch(e) {}
}
loadHistory();
setInterval(loadHistory, 10000);

// ── EXPORT ───────────────────────────────────────────
function exportReport() {
    const a = document.createElement("a");
    a.href     = "/export";
    a.download = "resq_mission_report.json";
    a.click();
}
</script>
</body>
</html>"""
