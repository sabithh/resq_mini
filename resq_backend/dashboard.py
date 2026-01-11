"""
dashboard.py
ResQ Drone – Futuristic Tactical Command Dashboard
Cyberpunk HUD / Glassmorphism
FINAL WORKING VERSION (Rescuer-aware)
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

body {
    margin: 0;
    background: var(--bg-color);
    color: #f8fafc;
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    flex-direction: column;
    height: 100vh;
}

header {
    padding: 18px 36px;
    background: rgba(2, 6, 23, 0.9);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

header .title {
    font-size: 20px;
    color: var(--neon-cyan);
    letter-spacing: 2px;
}

header .system-time {
    font-size: 12px;
    opacity: 0.4;
}

.main {
    flex: 1;
    display: grid;
    grid-template-columns: 2.8fr 1fr;
    gap: 20px;
    padding: 20px;
    overflow: hidden;
}

.feed-container {
    position: relative;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
}

.feed-container img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}

.sidebar {
    display: flex;
    flex-direction: column;
    gap: 15px;
    overflow-y: auto;
}

.section-title {
    font-size: 12px;
    color: var(--neon-cyan);
    letter-spacing: 3px;
    opacity: 0.7;
}

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
    background: rgba(0,0,0,0.35);
    border: 1px solid rgba(34,211,238,0.1);
    position: relative;
}

.dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
}

.footer {
    min-height: 64px;
    background: rgba(2, 6, 23, 0.95);
    border-top: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    letter-spacing: 2px;
}
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
    sysTime.innerText = "SYSTEM_TIME: " + n.toTimeString().slice(0,8);
}
setInterval(updateTime, 1000);

async function loadStatus() {
    feed.src = "/static/latest_annotated.jpg?t=" + Date.now();

    const res = await fetch("/status");
    const data = await res.json();

    victimList.innerHTML = "";

    if (map.children.length === 0) {
        for (let i = 0; i < 36; i++) {
            const c = document.createElement("div");
            c.className = "cell";
            map.appendChild(c);
        }
    }
    [...map.children].forEach(c => c.innerHTML = "");

    if (!data.victims || data.victims.length === 0) {
        decision.innerText = "AREA_CLEAR: NO RESCUE REQUIRED";
        decision.style.color = "var(--neon-green)";
        return;
    }

    // 🔥 Prioritize victims NOT rescued and NOT onway
    const order = { HIGH:0, MEDIUM:1, LOW:2 };
    const prioritized = data.victims
        .filter(v => !v.rescued)
        .sort((a,b) => (a.onway - b.onway) || (order[a.priority] - order[b.priority]));

    const highest = prioritized[0];

    data.victims.forEach(v => {
        const div = document.createElement("div");
        div.className = "card " + v.priority.toLowerCase();

        let statusHTML = "";
        if (v.rescued) {
            statusHTML = `<div style="color:#10b981;margin-top:6px;">✔️ RESCUED</div>`;
        } else if (v.onway) {
            statusHTML = `<div style="color:#fbbf24;margin-top:6px;">🚑 ${v.rescuer || "Responder"} ON THE WAY</div>`;
        } else {
            statusHTML = `<div style="color:#f43f5e;margin-top:6px;">❗ AWAITING RESPONSE</div>`;
        }

        div.innerHTML = `
            <strong>ID ${v.id}</strong>
            <div style="font-size:11px;opacity:.6">
                ${v.priority} | ${v.pose} | Grid ${v.grid}
            </div>
            ${statusHTML}
        `;
        victimList.appendChild(div);

        if (v.grid) {
            const idx = (v.grid[0]-1)*6 + (v.grid[1]-1);
            if (map.children[idx]) {
                const d = document.createElement("div");
                d.className = "dot";
                d.style.background =
                    v.priority === "HIGH" ? "#f43f5e" :
                    v.priority === "MEDIUM" ? "#fbbf24" :
                    "#10b981";
                map.children[idx].appendChild(d);
            }
        }
    });

    let active = data.victims.filter(v => !v.rescued);
    let onway = data.victims.filter(v => v.onway && !v.rescued);

    if (active.length > 0) {
        const highest = active[0];

        decision.innerHTML = `
            <span style="color:var(--neon-red);font-weight:bold">
                CRITICAL ACTION:
            </span>
            DEPLOY TO ID_${highest.id} [GRID ${highest.grid}]
        `;
        decision.style.color = "var(--neon-red)";

    } else if (onway.length > 0) {
        decision.innerHTML = `
            <span style="color:var(--neon-yellow);font-weight:bold">
                RESCUE IN PROGRESS
            </span>
        `;
        decision.style.color = "var(--neon-yellow)";

    } else {
        decision.innerHTML = `
            <span style="color:var(--neon-green);font-weight:bold">
                ALL TARGETS SECURED
            </span>
        `;
        decision.style.color = "var(--neon-green)";
    }
}

loadStatus();
setInterval(loadStatus, 2000);
</script>

</body>
</html>
"""
