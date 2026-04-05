// screens/camera_home.dart

import 'dart:async';
import 'dart:io';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_service.dart';
import '../widgets/telemetry_overlay.dart';
import 'settings_screen.dart';

late List<CameraDescription> cameras;

class CameraHome extends StatefulWidget {
  const CameraHome({super.key});
  @override
  State<CameraHome> createState() => _CameraHomeState();
}

class _CameraHomeState extends State<CameraHome>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  CameraController? _controller;
  bool _isStreaming  = false;
  bool _isSending    = false;
  bool _thermalMode  = false;
  String _thermalPreset = 'clahe'; // 'clahe' | 'false_color' | 'raw'
  Timer? _frameTimer;

  String _statusMessage = 'SYSTEM READY';
  Color  _statusColor   = Colors.cyanAccent;

  final String _droneId = 'DRONE_1';

  late AnimationController _scanController;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initCamera();
    _scanController = AnimationController(
        vsync: this, duration: const Duration(seconds: 3));
  }

  Future<void> _initCamera() async {
    if (cameras.isEmpty) {
      if (mounted) {
        setState(() {
          _statusMessage = 'NO CAMERA FOUND';
          _statusColor = Colors.redAccent;
        });
      }
      return;
    }
    _controller = CameraController(
        cameras.first, ResolutionPreset.medium, enableAudio: false);
    await _controller!.initialize();
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _scanController.dispose();
    _frameTimer?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // If the app is minimized/paused, release the camera to save battery
    // and prevent crashes.
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused) {
      if (_isStreaming) _stopLiveStream();
      _controller?.dispose();
      _controller = null;
      if (mounted) setState(() {});
    } else if (state == AppLifecycleState.resumed) {
      // Re-initialize camera on foreground
      _initCamera();
    }
  }

  // ── STREAM ────────────────────────────────────────
  void _startLiveStream() {
    setState(() {
      _isStreaming  = true;
      _statusMessage = 'LIVE FEED ACTIVE';
      _statusColor   = Colors.greenAccent;
    });
    _scanController.repeat(reverse: true);
    _frameTimer = Timer.periodic(const Duration(milliseconds: 1200), (_) async {
      if (!_controller!.value.isInitialized || _isSending) return;
      final pic = await _controller!.takePicture();
      await _sendCapture(File(pic.path));
    });
  }

  void _stopLiveStream() {
    _frameTimer?.cancel();
    _scanController.stop();
    setState(() {
      _isStreaming   = false;
      _statusMessage = 'SYSTEM IDLE';
      _statusColor   = Colors.cyanAccent;
    });
  }

  // ── SEND ──────────────────────────────────────────
  Future<void> _sendCapture(File file) async {
    if (_isSending) return;
    _setStatus(true,
        _thermalMode ? 'THERMAL SCAN...' : 'UPLOADING IMAGE...', Colors.orangeAccent);
    try {
      final res = _thermalMode
          ? await ApiService.sendImageForThermal(file,
              mode: _thermalPreset, droneId: _droneId)
          : await ApiService.sendImageForDetect(file, droneId: _droneId);
      _setStatus(false,
          res.statusCode == 200
              ? (_thermalMode ? 'THERMAL PROCESSED' : 'IMAGE PROCESSED')
              : 'UPLOAD ERROR',
          res.statusCode == 200 ? Colors.greenAccent : Colors.redAccent);
    } catch (_) {
      _setStatus(false, 'CONNECTION LOST', Colors.redAccent);
    }
  }

  Future<void> _pickFile({required bool isVideo}) async {
    final picker = ImagePicker();
    final file   = isVideo
        ? await picker.pickVideo(source: ImageSource.gallery)
        : await picker.pickImage(source: ImageSource.gallery);
    if (file == null) return;
    if (isVideo) {
      _uploadVideo(File(file.path));
    } else {
      _sendCapture(File(file.path));
    }
  }

  Future<void> _uploadVideo(File videoFile) async {
    if (_isSending) return;
    _setStatus(true, 'UPLOADING VIDEO...', Colors.orangeAccent);
    try {
      final res = await ApiService.uploadVideo(videoFile);
      _setStatus(false,
          res.statusCode == 200 ? 'VIDEO UPLOADED' : 'VIDEO UPLOAD FAILED',
          res.statusCode == 200 ? Colors.greenAccent : Colors.redAccent);
    } catch (_) {
      _setStatus(false, 'CONNECTION ERROR', Colors.redAccent);
    }
  }

  void _setStatus(bool busy, String msg, Color color) {
    if (!mounted) return;
    setState(() {
      _isSending     = busy;
      _statusMessage = msg;
      _statusColor   = color;
    });
  }

  // ── UI ────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    if (_controller == null || !_controller!.value.isInitialized) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator(color: Colors.cyanAccent)),
      );
    }
    return Scaffold(
      body: Stack(children: [
        Positioned.fill(
          child: Container(
            color: Colors.black,
            child: Center(
              child: AspectRatio(
                aspectRatio: MediaQuery.of(context).orientation == Orientation.portrait
                    ? 1 / _controller!.value.aspectRatio
                    : _controller!.value.aspectRatio,
                child: CameraPreview(_controller!),
              ),
            ),
          ),
        ),

        if (_isStreaming)
          AnimatedBuilder(
            animation: _scanController,
            builder: (_, __) => Positioned(
              top: MediaQuery.of(context).size.height * _scanController.value,
              left: 0, right: 0,
              child: Container(height: 2, color: Colors.cyanAccent),
            ),
          ),

        Positioned(top: 50, left: 20, right: 20, child: _buildTopHud()),
        const Positioned.fill(child: TelemetryOverlay()),
        Positioned(bottom: 30, left: 20, right: 20, child: _buildBottomDock()),
      ]),
    );
  }

  Widget _buildTopHud() => ClipRRect(
    borderRadius: BorderRadius.circular(15),
    child: BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.4),
          border: Border.all(color: _statusColor.withValues(alpha: 0.5)),
          borderRadius: BorderRadius.circular(15),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Text(_droneId,
                    style: TextStyle(
                        color: Colors.cyanAccent.withValues(alpha: 0.7),
                        fontSize: 10, letterSpacing: 2)),
                if (_thermalMode) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.amber.withValues(alpha: 0.2),
                      border: Border.all(color: Colors.amber, width: 0.5),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(_thermalPreset.toUpperCase(),
                        style: const TextStyle(color: Colors.amber, fontSize: 8, letterSpacing: 1)),
                  ),
                ],
              ]),
              Text(_statusMessage,
                  style: TextStyle(
                      color: _statusColor, fontSize: 18, fontWeight: FontWeight.bold)),
            ]),
            if (_isSending)
              const SizedBox(
                  width: 20, height: 20,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.orangeAccent)),
          ],
        ),
      ),
    ),
  );

  Widget _buildBottomDock() => ClipRRect(
    borderRadius: BorderRadius.circular(25),
    child: BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(25),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _hudButton(Icons.image_search, 'IMG',
                () { if (!_isSending) _pickFile(isVideo: false); }),
            _mainActionButton(),
            _hudButton(Icons.video_library, 'VID',
                () { if (!_isSending) _pickFile(isVideo: true); }),
            _thermalButton(),
            _hudButton(Icons.settings, 'CFG', () {
              Navigator.push(context,
                  MaterialPageRoute(builder: (_) => const SettingsScreen()));
            }),
          ],
        ),
      ),
    ),
  );

  Widget _mainActionButton() => GestureDetector(
    onTap: _isSending ? null : (_isStreaming ? _stopLiveStream : _startLiveStream),
    child: Container(
      height: 70, width: 70,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(
            color: _isStreaming ? Colors.redAccent : Colors.cyanAccent, width: 2),
      ),
      child: Icon(
          _isStreaming ? Icons.stop : Icons.sensors,
          color: _isStreaming ? Colors.redAccent : Colors.cyanAccent,
          size: 35),
    ),
  );

  Widget _hudButton(IconData icon, String label, VoidCallback onTap) =>
      InkWell(
        onTap: onTap,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, color: Colors.white70),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 10)),
        ]),
      );

  Widget _thermalButton() {
    final active = _thermalMode;
    return GestureDetector(
      onTap: () {
        setState(() => _thermalMode = !_thermalMode);
      },
      onLongPress: () {
        // Cycle through presets on long press
        const presets = ['clahe', 'false_color', 'raw'];
        final next = (presets.indexOf(_thermalPreset) + 1) % presets.length;
        setState(() => _thermalPreset = presets[next]);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Thermal preset: ${_thermalPreset.toUpperCase()}',
              style: const TextStyle(color: Colors.black)),
          backgroundColor: Colors.amber,
          duration: const Duration(seconds: 1),
        ));
      },
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: active ? Colors.amber.withValues(alpha: 0.2) : Colors.transparent,
            shape: BoxShape.circle,
            border: Border.all(
              color: active ? Colors.amber : Colors.white30,
              width: active ? 1.5 : 0.5,
            ),
          ),
          child: Icon(Icons.thermostat,
              color: active ? Colors.amber : Colors.white54, size: 20),
        ),
        const SizedBox(height: 4),
        Text('THML',
            style: TextStyle(
                color: active ? Colors.amber : Colors.white54, fontSize: 10)),
      ]),
    );
  }
}
