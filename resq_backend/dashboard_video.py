"""
dashboard_video.py

ResQ – Video + Image Control Dashboard
- Faster MJPEG streaming
- Upload video OR image
- Send image for detection (no phone needed)
"""

def get_video_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ResQ | Video & Image Control</title>
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
    background: var(--bg); color: #f8fafc; font-family: 'JetBrains Mono', monospace;
    display: flex; flex-direction: column; height: 100vh; overflow: hidden;
}

/* ── HEADER ──────────────────────────────── */
header {
    padding: 14px 28px; background: rgba(2,6,23,0.95); border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;
}
.title { font-size: 18px; color: var(--cyan); letter-spacing: 2px; }
.header-right { display: flex; align-items: center; gap: 12px; }

.nav-btn {
    padding: 7px 16px; border-radius: 6px; font-family: inherit;
    font-size: 10px; letter-spacing: 2px; cursor: pointer; text-decoration: none;
    border: 1px solid; transition: all .2s; font-weight: 700;
}
.nav-btn-home { border-color: rgba(255,255,255,0.2); background: rgba(255,255,255,0.05); color: #fff; }
.nav-btn-home:hover { background: rgba(255,255,255,0.15); }
.nav-btn-thermal { border-color: rgba(255,106,0,0.4); background: rgba(255,106,0,0.08); color: #ff6a00; }
.nav-btn-thermal:hover { background: rgba(255,106,0,0.2); }
.nav-btn-video { border-color: rgba(34,211,238,0.4); background: rgba(34,211,238,0.06); color: var(--cyan); }
.nav-btn-video:hover { background: rgba(34,211,238,0.15); }

/* ── MAIN ────────────────────────────────── */
.main {
    flex: 1; display: grid; grid-template-columns: 2.6fr 1fr; gap: 16px; padding: 16px; overflow: hidden;
}

/* ── FEED ────────────────────────────────── */
.video-panel {
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
    display: flex; flex-direction: column; position: relative;
}
.feed-label {
    padding: 8px 14px; font-size: 10px; color: rgba(255,255,255,0.3);
    letter-spacing: 2px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
}
.video-panel img { width: 100%; height: 100%; object-fit: contain; background: #000; min-height: 0; flex: 1; }

/* ── CONTROLS ────────────────────────────── */
.control-panel {
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; display: flex; flex-direction: column; gap: 16px; overflow-y: auto;
}
.section-title { font-size: 10px; color: var(--cyan); letter-spacing: 3px; opacity: 0.7; border-bottom: 1px solid var(--border); padding-bottom: 6px; }

input[type="file"] {
    font-size: 10px; color: var(--cyan); padding: 8px; border: 1px dashed var(--border); border-radius: 6px; width: 100%; cursor: pointer; background: rgba(34,211,238,0.05);
}

.act-btn {
    width: 100%; padding: 10px; font-size: 11px; letter-spacing: 2px; border-radius: 6px; cursor: pointer;
    border: 1px solid; background: rgba(255,255,255,0.05); color: #fff; font-family: inherit; transition: .2s; font-weight: 700;
}
.act-btn:hover { background: rgba(255,255,255,0.1); }
.play-btn { border-color: var(--green); color: var(--green); background: rgba(16,185,129,0.1); }
.play-btn:hover { background: rgba(16,185,129,0.2); }
.stop-btn { border-color: var(--red); color: var(--red); background: rgba(244,63,94,0.1); }
.stop-btn:hover { background: rgba(244,63,94,0.2); }
.img-btn { border-color: #a855f7; color: #c084fc; background: rgba(168,85,247,0.1); }
.img-btn:hover { background: rgba(168,85,247,0.2); }

.status-box {
    margin-top: auto; padding: 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 11px; color: var(--cyan); background: rgba(34,211,238,0.05); letter-spacing: 1px;
}
</style>
</head>
<body>
<!-- HEADER -->
<header>
  <div class="title" style="color:var(--cyan)">VIDEO_&_IMAGE_CONTROL_LAB</div>
  <div class="header-right">
    <a href="/dashboard"         class="nav-btn nav-btn-home">🏠 HOME</a>
    <a href="/dashboard/thermal" class="nav-btn nav-btn-thermal">🌡️ THERMAL</a>
    <a href="/dashboard/video"   class="nav-btn nav-btn-video">🎥 VIDEO</a>
  </div>
</header>

<div class="main">
    <!-- LIVE FEED -->
    <div class="video-panel">
        <div class="feed-label">
            <span>MJPEG STREAM</span>
        </div>
        <img id="stream" src="/video-stream" alt="Live Stream">
    </div>

    <!-- CONTROLS -->
    <div class="control-panel">
        <div>
            <div class="section-title" style="margin-bottom:12px;">📹 VIDEO UPLOAD & PLAYBACK</div>
            <input type="file" id="videoFile" accept="video/*" style="margin-bottom:12px;">
            <div style="display:flex;flex-direction:column;gap:8px;">
                <button class="act-btn" onclick="uploadVideo()">📤 UPLOAD VIDEO</button>
                <button class="act-btn play-btn" onclick="startStream()">▶️ START STREAM</button>
                <button class="act-btn" onclick="restartStream()" style="border-color:var(--yellow);color:var(--yellow);background:rgba(251,191,36,0.1);">🔁 RESTART STREAM</button>
                <button class="act-btn stop-btn" onclick="stopStream()">⏹ STOP STREAM</button>
            </div>
        </div>

        <div style="margin-top:20px;">
            <div class="section-title" style="margin-bottom:12px;">📸 STATIC IMAGE DETECTION</div>
            <input type="file" id="imageFile" accept="image/*" style="margin-bottom:12px;">
            <button class="act-btn img-btn" onclick="sendImage()">🚀 RUN DETECTION ON IMAGE</button>
        </div>

        <div class="status-box" id="status">SYS_STATUS: IDLE</div>
    </div>
</div>

<script>
function setStatus(text) {
    document.getElementById("status").innerText = "SYS_STATUS: " + text.toUpperCase();
}

async function uploadVideo() {
    const file = videoFile.files[0];
    if (!file) return alert("Select a video");
    const fd = new FormData(); fd.append("file", file);
    setStatus("Uploading video...");
    const res = await fetch("/upload-video", { method: "POST", body: fd });
    setStatus(res.ok ? "Video uploaded" : "Upload failed");
}

async function startStream() {
    const res = await fetch("/start-stream", { method: "POST" });
    setStatus(res.ok ? "Streaming started" : "Start failed");
}

async function restartStream() {
    const res = await fetch("/restart-stream", { method: "POST" });
    setStatus(res.ok ? "Restarted" : "Restart failed");
}

async function stopStream() {
    const res = await fetch("/stop-stream", { method: "POST" });
    setStatus(res.ok ? "Stopped" : "Stop failed");
}

async function sendImage() {
    const file = imageFile.files[0];
    if (!file) return alert("Select an image");
    const fd = new FormData(); fd.append("file", file);
    setStatus("Processing image...");
    const res = await fetch("/detect", { method: "POST", body: fd });
    setStatus(res.ok ? "Image processed ✔️" : "Image failed ❌");
}
</script>
</body>
</html>"""
