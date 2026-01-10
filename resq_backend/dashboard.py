"""
dashboard.py
ResQ Drone – Futuristic Tactical Command Dashboard
Theme: Cyberpunk HUD / Glassmorphism
(FINAL FIXED LAYOUT VERSION)
"""

def get_dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ResQ Drone | Tactical Command</title>

<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

:root {
    --bg-color: #05070a;
    --card-bg: rgba(15, 23, 42, 0.6);
    --neon-cyan: #22d3ee;
    --neon-red: #f43f5e;
    --neon-yellow: #fbbf24;
    --neon-green: #10b981;
    --border-color: rgba(34, 211, 238, 0.2);
}

/* 🔥 FIX 1: Proper vertical layout */
body {
    margin: 0;
    background: var(--bg-color);
    color: #f8fafc;
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    flex-direction: column;
    height: 100vh;
    background-image:
        radial-gradient(circle at 50% 50%, rgba(34, 211, 238, 0.05) 0%, transparent 80%);
}

/* --- HEADER --- */
header {
    padding: 20px 40px;
    background: rgba(2, 6, 23, 0.85);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
    letter-spacing: 2px;
}

header .title {
    font-size: 20px;
    font-weight: 700;
    color: var(--neon-cyan);
    text-shadow: 0 0 10px rgba(34, 211, 238, 0.5);
}

header .system-time {
    font-size: 12px;
    color: rgba(255,255,255,0.4);
}

/* 🔥 FIX 2: Main grows naturally */
.main {
    flex: 1;
    display: grid;
    grid-template-columns: 2.8fr 1fr;
    gap: 20px;
    padding: 20px;
    overflow: hidden;
}

/* --- FEED CONTAINER --- */
.feed-container {
    position: relative;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
}

.feed-container::after {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--neon-cyan);
    box-shadow: 0 0 15px var(--neon-cyan);
    animation: scan 4s linear infinite;
    opacity: 0.5;
}

@keyframes scan {
    0% { top: 0%; }
    100% { top: 100%; }
}

.feed-container img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}

/* --- SIDEBAR --- */
.sidebar {
    display: flex;
    flex-direction: column;
    gap: 15px;
    overflow-y: auto;
}

.section-title {
    font-size: 12px;
    text-transform: uppercase;
    color: var(--neon-cyan);
    letter-spacing: 3px;
    opacity: 0.8;
}

/* --- VICTIM CARDS --- */
.card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-left: 4px solid transparent;
    border-radius: 8px;
    padding: 14px;
    font-size: 13px;
}

.high { border-left-color: var(--neon-red); }
.medium { border-left-color: var(--neon-yellow); }
.low { border-left-color: var(--neon-green); }

/* --- TACTICAL MAP --- */
.map-container {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 15px;
    display: flex;
    justify-content: center;
}

.map-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    grid-template-rows: repeat(6, 1fr);
    gap: 4px;
    width: 240px;
    height: 240px;
}

.cell {
    border: 1px solid rgba(34, 211, 238, 0.1);
    background: rgba(0,0,0,0.35);
    position: relative;
}

.dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    box-shadow: 0 0 10px currentColor;
}

/* 🔥 FIX 3: Footer always visible */
.footer {
    min-height: 64px;
    padding: 12px 20px;
    background: rgba(2, 6, 23, 0.95);
    border-top: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    letter-spacing: 2px;
    text-align: center;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: var(--border-color); }
</style>
</head>

<body>

<header>
    <div class="title">RESQ_COMMAND_CENTER_V4</div>
    <div class="system-time" id="sysTime">--:--:--</div>
</header>

<div class="main">
    <div class="feed-container">
        <img id="feed" src="/static/latest_annotated.jpg">
        <div style="position:absolute;top:10px;left:10px;background:#f43f5e;padding:2px 8px;font-size:10px;border-radius:4px;">
            LIVE FEED
        </div>
    </div>

    <div class="sidebar">
        <div class="section-title">Detected Targets</div>
        <div id="victimList"></div>

        <div class="section-title">Tactical Grid</div>
        <div class="map-container">
            <div id="map" class="map-grid"></div>
        </div>
    </div>
</div>

<div class="footer" id="decision">
    STANDBY: SYSTEM ANALYSIS IN PROGRESS
</div>

<script>
function updateTime() {
    const n = new Date();
    sysTime.innerText =
        "SYSTEM_TIME: " +
        n.toTimeString().slice(0, 8);
}
setInterval(updateTime, 1000);

async function loadStatus() {
    feed.src = "/static/latest_annotated.jpg?t=" + Date.now();
    const res = await fetch("/status");
    const data = await res.json();

    victimList.innerHTML = "";
    if (map.children.length === 0) {
        for (let i = 0; i < 36; i++) map.appendChild(document.createElement("div")).className = "cell";
    }
    [...map.children].forEach(c => c.innerHTML = "");

    if (!data.victims || data.victims.length === 0) {
        decision.innerText = "AREA_CLEAR: NO RESCUE REQUIRED";
        decision.style.color = "var(--neon-green)";
        return;
    }

    let active = data.victims.filter(v => !v.rescued);
    let highest = active[0];

    data.victims.forEach(v => {
        const div = document.createElement("div");
        div.className = "card " + v.priority.toLowerCase();
        div.innerHTML = `
            <strong>ID ${v.id}</strong>
            <div style="font-size:11px;opacity:.6">
                ${v.priority} | ${v.pose} | Grid ${v.grid}
            </div>`;
        victimList.appendChild(div);

        if (v.grid) {
            const idx = (v.grid[0]-1)*6 + (v.grid[1]-1);
            if (map.children[idx]) {
                const d = document.createElement("div");
                d.className = "dot";
                d.style.color =
                    v.priority === "HIGH" ? "var(--neon-red)" :
                    v.priority === "MEDIUM" ? "var(--neon-yellow)" :
                    "var(--neon-green)";
                d.style.background = "currentColor";
                map.children[idx].appendChild(d);
            }
        }
    });

    decision.innerHTML =
        `<span style="color:var(--neon-red);font-weight:bold">
        CRITICAL ACTION:
        </span>&nbsp;DEPLOY TO ID_${highest.id} [GRID ${highest.grid}]`;
}

loadStatus();
setInterval(loadStatus, 2000);
</script>

</body>
</html>
"""
