"""
dashboard.py

Professional Control Room UI for ResQ Drone System
"""

def get_dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ResQ Drone – Control Room</title>
<meta http-equiv="refresh" content="2">

<style>
body {
    margin: 0;
    background: #0b0f14;
    color: #e5e7eb;
    font-family: Arial, sans-serif;
}

header {
    padding: 15px 30px;
    background: #020617;
    border-bottom: 2px solid #1e293b;
    font-size: 22px;
    color: #38bdf8;
}

.main {
    display: grid;
    grid-template-columns: 2.5fr 1fr;
    gap: 15px;
    padding: 15px;
}

.feed {
    background: #020617;
    border-radius: 10px;
    padding: 10px;
}

.feed img {
    width: 100%;
    max-height: 70vh;
    object-fit: contain;
    border-radius: 8px;
}

.sidebar {
    background: #020617;
    border-radius: 10px;
    padding: 10px;
    overflow-y: auto;
    max-height: 75vh;
}

.card {
    background: #020617;
    border: 2px solid #1e293b;
    border-left-width: 6px;
    border-radius: 8px;
    padding: 10px;
    margin-bottom: 10px;
    font-size: 14px;
}

.high { border-left-color: #ef4444; }
.medium { border-left-color: #facc15; }
.low { border-left-color: #22c55e; }

.footer {
    background: #020617;
    padding: 15px;
    border-top: 2px solid #1e293b;
    font-size: 16px;
    text-align: center;
    color: #f87171;
}
</style>
</head>

<body>

<header>🚨 ResQ Drone – Control Room</header>

<div class="main">

    <!-- LIVE FEED -->
    <div class="feed">
        <img src="/static/latest_annotated.jpg" onerror="this.src='/static/latest.jpg'">
    </div>

    <!-- VICTIM LIST -->
    <div class="sidebar" id="victimList">
        Loading victims...
    </div>

</div>

<!-- RESCUE DECISION -->
<div class="footer" id="decision">
    Awaiting detection...
</div>

<script>
async function loadStatus() {
    const res = await fetch('/status');
    const data = await res.json();

    const list = document.getElementById('victimList');
    const decision = document.getElementById('decision');
    list.innerHTML = "";

    if (!data.victims || data.victims.length === 0) {
        list.innerHTML = "<p>No victims detected</p>";
        decision.innerText = "No rescue required";
        return;
    }

    let highest = data.victims[0];

    data.victims.forEach(v => {
        const div = document.createElement('div');
        div.className = "card " + v.priority.toLowerCase();
        div.innerHTML = `
            <strong>Victim ID:</strong> ${v.id}<br>
            <strong>Priority:</strong> ${v.priority}<br>
            <strong>Grid:</strong> [${v.grid}]<br>
            <strong>Risk:</strong> ${v.risk_score}
        `;
        list.appendChild(div);

        if (v.priority === "HIGH") highest = v;
    });

    decision.innerHTML =
        "🚑 <strong>RESCUE FIRST:</strong> Victim ID " +
        highest.id +
        " (" + highest.priority + ", Grid " + highest.grid + ")";
}

loadStatus();
setInterval(loadStatus, 2000);
</script>

</body>
</html>
"""

