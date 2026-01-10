"""
dashboard_video.py

Video Streaming Control Dashboard for ResQ
- Shows the uploaded video (MJPEG stream)
- Operator-controlled playback
- Upload / Play / Restart / Stop
"""

def get_video_dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ResQ – Video Streaming Dashboard</title>

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
    margin-bottom: 15px;
    color: #38bdf8;
}

.control-panel input[type="file"] {
    width: 100%;
    margin-bottom: 15px;
    color: #e5e7eb;
}

.control-panel button {
    width: 100%;
    padding: 12px;
    margin-bottom: 10px;
    font-size: 16px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
}

.upload-btn {
    background: #2563eb;
    color: white;
}

.play-btn {
    background: #16a34a;
    color: white;
}

.restart-btn {
    background: #f59e0b;
    color: black;
}

.stop-btn {
    background: #dc2626;
    color: white;
}

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

<header>🎥 ResQ – Video Streaming Control Room</header>

<div class="main">

    <!-- VIDEO STREAM -->
    <div class="video-panel">
        <img src="/video-stream" alt="Live Video Stream">
    </div>

    <!-- CONTROLS -->
    <div class="control-panel">
        <h3>Video Controls</h3>

        <input type="file" id="videoFile" accept="video/*">

        <button class="upload-btn" onclick="uploadVideo()">📤 Upload Video</button>
        <button class="play-btn" onclick="startStream()">▶️ Start Stream</button>
        <button class="restart-btn" onclick="restartStream()">🔁 Restart Video</button>
        <button class="stop-btn" onclick="stopStream()">⏹ Stop Stream</button>

        <div class="status-box" id="status">
            Status: Idle
        </div>
    </div>

</div>

<script>
async function uploadVideo() {
    const fileInput = document.getElementById("videoFile");
    const file = fileInput.files[0];

    if (!file) {
        alert("Please select a video file");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setStatus("Uploading video...");

    const res = await fetch("/upload-video", {
        method: "POST",
        body: formData
    });

    if (res.ok) {
        setStatus("Video uploaded. Ready to play.");
    } else {
        setStatus("Upload failed.");
    }
}

async function startStream() {
    const res = await fetch("/start-stream", { method: "POST" });
    if (res.ok) {
        setStatus("Streaming video...");
    } else {
        setStatus("Failed to start stream.");
    }
}

async function restartStream() {
    const res = await fetch("/restart-stream", { method: "POST" });
    if (res.ok) {
        setStatus("Video restarted from beginning.");
    } else {
        setStatus("Failed to restart video.");
    }
}

async function stopStream() {
    const res = await fetch("/stop-stream", { method: "POST" });
    if (res.ok) {
        setStatus("Stream stopped.");
    } else {
        setStatus("Failed to stop stream.");
    }
}

function setStatus(text) {
    document.getElementById("status").innerText = "Status: " + text;
}
</script>

</body>
</html>
"""
