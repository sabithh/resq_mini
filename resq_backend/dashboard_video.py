"""
dashboard_video.py

ResQ – Video + Image Control Dashboard
- Faster MJPEG streaming
- Upload video OR image
- Send image for detection (no phone needed)
"""

def get_video_dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ResQ – Video & Image Control</title>

<style>
body {
    margin: 0;
    background: #020617;
    color: #e5e7eb;
    font-family: Arial, sans-serif;
}

header {
    padding: 15px 30px;
    background: #020617;
    border-bottom: 2px solid #1e293b;
    font-size: 22px;
    color: #22c55e;
}

.main {
    display: grid;
    grid-template-columns: 2.5fr 1fr;
    gap: 15px;
    padding: 15px;
}

.video-panel {
    background: #020617;
    padding: 10px;
    border-radius: 10px;
    border: 2px solid #1e293b;
}

.video-panel img {
    width: 100%;
    max-height: 75vh;
    object-fit: contain;
    border-radius: 8px;
    background: #000;
}

.control-panel {
    background: #020617;
    padding: 15px;
    border-radius: 10px;
    border: 2px solid #1e293b;
}

.control-panel h3 {
    margin-top: 0;
    margin-bottom: 10px;
    color: #38bdf8;
}

.control-panel input[type="file"] {
    width: 100%;
    margin-bottom: 10px;
    color: #e5e7eb;
}

.control-panel button {
    width: 100%;
    padding: 12px;
    margin-bottom: 10px;
    font-size: 15px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
}

.upload-btn { background: #2563eb; color: white; }
.play-btn { background: #16a34a; color: white; }
.restart-btn { background: #f59e0b; color: black; }
.stop-btn { background: #dc2626; color: white; }
.image-btn { background: #7c3aed; color: white; }

.status-box {
    margin-top: 15px;
    padding: 10px;
    border-radius: 6px;
    background: #020617;
    border: 1px solid #1e293b;
    font-size: 14px;
}
</style>
</head>

<body>

<header>🎥 ResQ – Video & Image Control Room</header>

<div class="main">

    <!-- LIVE STREAM -->
    <div class="video-panel">
        <img id="stream" src="/video-stream" alt="Live Stream">
    </div>

    <!-- CONTROLS -->
    <div class="control-panel">

        <h3>📹 Video Controls</h3>
        <input type="file" id="videoFile" accept="video/*">
        <button class="upload-btn" onclick="uploadVideo()">📤 Upload Video</button>
        <button class="play-btn" onclick="startStream()">▶️ Start Stream</button>
        <button class="restart-btn" onclick="restartStream()">🔁 Restart Video</button>
        <button class="stop-btn" onclick="stopStream()">⏹ Stop Stream</button>

        <hr style="border:1px solid #1e293b; margin:15px 0;">

        <h3>📸 Image Detection</h3>
        <input type="file" id="imageFile" accept="image/*">
        <button class="image-btn" onclick="sendImage()">🚀 Send Image</button>

        <div class="status-box" id="status">Status: Idle</div>
    </div>

</div>

<script>
function setStatus(text) {
    document.getElementById("status").innerText = "Status: " + text;
}

// ---------------- VIDEO ----------------

async function uploadVideo() {
    const file = videoFile.files[0];
    if (!file) return alert("Select a video");

    const fd = new FormData();
    fd.append("file", file);

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

// ---------------- IMAGE ----------------

async function sendImage() {
    const file = imageFile.files[0];
    if (!file) return alert("Select an image");

    const fd = new FormData();
    fd.append("file", file);

    setStatus("Sending image for detection...");
    const res = await fetch("/detect", {
        method: "POST",
        body: fd
    });

    setStatus(res.ok ? "Image processed ✔️" : "Image failed ❌");
}
</script>

</body>
</html>
"""
