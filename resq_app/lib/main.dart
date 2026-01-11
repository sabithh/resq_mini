import 'dart:async';
import 'dart:io';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;

late List<CameraDescription> cameras;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  cameras = await availableCameras();
  runApp(const ResQApp());
}

class ResQApp extends StatelessWidget {
  const ResQApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'ResQ Drone',
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: Colors.black,
      ),
      // Set the SplashScreen as the initial home
      home: const SplashScreen(),
    );
  }
}

// --- NEW SPLASH SCREEN CLASS ---
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.2).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );

    // Navigate to CameraHome after 3.5 seconds
    Timer(const Duration(milliseconds: 3500), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (context, animation, secondaryAnimation) => const CameraHome(),
            transitionsBuilder: (context, animation, secondaryAnimation, child) {
              return FadeTransition(opacity: animation, child: child);
            },
            transitionDuration: const Duration(milliseconds: 1000),
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Background Grid Effect
          Opacity(
            opacity: 0.1,
            child: CustomPaint(
              size: MediaQuery.of(context).size,
              painter: GridPainter(),
            ),
          ),
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Pulsing Drone Icon
                ScaleTransition(
                  scale: _pulseAnimation,
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.cyanAccent, width: 2),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.cyanAccent.withOpacity(0.3),
                          blurRadius: 20,
                          spreadRadius: 5,
                        )
                      ],
                    ),
                    child: const Icon(
                      Icons.navigation_rounded,
                      size: 80,
                      color: Colors.cyanAccent,
                    ),
                  ),
                ),
                const SizedBox(height: 40),
                // Cyberpunk Title
                const Text(
                  "RESQ_SYSTEMS",
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 8,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  "ESTABLISHING SECURE LINK...",
                  style: TextStyle(
                    color: Colors.cyanAccent.withOpacity(0.6),
                    fontSize: 10,
                    letterSpacing: 2,
                  ),
                ),
                const SizedBox(height: 50),
                // Futuristic Loading Bar
                SizedBox(
                  width: 200,
                  child: Column(
                    children: [
                      const LinearProgressIndicator(
                        backgroundColor: Colors.white10,
                        color: Colors.cyanAccent,
                        minHeight: 2,
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: const [
                          Text("V_4.02", style: TextStyle(color: Colors.white24, fontSize: 8)),
                          Text("RUNNING_DIAGNOSTICS", style: TextStyle(color: Colors.white24, fontSize: 8)),
                        ],
                      )
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// Simple Painter to create a futuristic background grid
class GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.cyanAccent
      ..strokeWidth = 0.5;

    for (var i = 0; i < size.width; i += 40) {
      canvas.drawLine(Offset(i.toDouble(), 0), Offset(i.toDouble(), size.height), paint);
    }
    for (var i = 0; i < size.height; i += 40) {
      canvas.drawLine(Offset(0, i.toDouble()), Offset(size.width, i.toDouble()), paint);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => false;
}

class CameraHome extends StatefulWidget {
  const CameraHome({super.key});

  @override
  State<CameraHome> createState() => _CameraHomeState();
}

class _CameraHomeState extends State<CameraHome>
    with SingleTickerProviderStateMixin {
  CameraController? _controller;
  bool _isStreaming = false;
  bool _isSending = false;
  Timer? _frameTimer;

  String _statusMessage = "SYSTEM READY";
  Color _statusColor = Colors.cyanAccent;

  late AnimationController _scanController;

  // ✅ FIXED BACKEND URL
  static const String BACKEND_BASE_URL = 'http://192.168.1.2:8000';
  static const String BACKEND_IMAGE_URL = '$BACKEND_BASE_URL/detect';
  static const String BACKEND_VIDEO_URL = '$BACKEND_BASE_URL/upload-video';

  @override
  void initState() {
    super.initState();
    _initCamera();
    _scanController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    );
  }

  Future<void> _initCamera() async {
    _controller = CameraController(
      cameras.first,
      ResolutionPreset.medium, // ✅ SAFER FOR STREAMING
      enableAudio: false,
    );
    await _controller!.initialize();
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _scanController.dispose();
    _frameTimer?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  // ---------------- SEND DATA ----------------
  Future<void> _sendData(File file, String url, bool isVideo) async {
    if (_isSending) return;

    setState(() {
      _isSending = true;
      _statusMessage =
          isVideo ? "UPLOADING VIDEO..." : "UPLOADING IMAGE...";
      _statusColor = Colors.orangeAccent;
    });

    try {
      var request = http.MultipartRequest('POST', Uri.parse(url));
      request.files.add(await http.MultipartFile.fromPath('file', file.path));
      final response = await request.send();

      setState(() {
        if (response.statusCode == 200) {
          _statusMessage =
              isVideo ? "VIDEO ANALYSIS COMPLETE" : "IMAGE PROCESSED";
          _statusColor = Colors.greenAccent;
        } else {
          _statusMessage = "UPLOAD ERROR";
          _statusColor = Colors.redAccent;
        }
      });
    } catch (_) {
      setState(() {
        _statusMessage = "CONNECTION LOST";
        _statusColor = Colors.redAccent;
      });
    } finally {
      _isSending = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_controller == null || !_controller!.value.isInitialized) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: Colors.cyanAccent),
        ),
      );
    }

    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(child: CameraPreview(_controller!)),

          if (_isStreaming)
            AnimatedBuilder(
              animation: _scanController,
              builder: (context, child) {
                return Positioned(
                  top: MediaQuery.of(context).size.height *
                      _scanController.value,
                  left: 0,
                  right: 0,
                  child: Container(
                    height: 2,
                    color: Colors.cyanAccent,
                  ),
                );
              },
            ),

          Positioned(top: 50, left: 20, right: 20, child: _buildTopHud()),
          
          // 5. TELEMETRY OVERLAY
          Positioned.fill(
            child: const TelemetryOverlay(),
          ),
          
          Positioned(bottom: 30, left: 20, right: 20, child: _buildBottomDock()),
        ],
      ),
    );
  }

  // ---------------- UI COMPONENTS ----------------
  Widget _buildTopHud() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(15),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.4),
            border: Border.all(color: _statusColor.withOpacity(0.5)),
            borderRadius: BorderRadius.circular(15),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("RESQ_DRONE_v1.0",
                      style: TextStyle(
                          color: Colors.cyanAccent.withOpacity(0.7),
                          fontSize: 10,
                          letterSpacing: 2)),
                  Text(_statusMessage,
                      style: TextStyle(
                          color: _statusColor,
                          fontSize: 18,
                          fontWeight: FontWeight.bold)),
                ],
              ),
              if (_isSending)
                const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.orangeAccent,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBottomDock() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(25),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 20),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.05),
            borderRadius: BorderRadius.circular(25),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _hudButton(Icons.image_search, "IMG", () {
                if (_isSending) return;
                _pickFile(isVideo: false);
              }),
              _mainActionButton(),
              _hudButton(Icons.video_library, "VID", () {
                if (_isSending) return;
                _pickFile(isVideo: true);
              }),
            ],
          ),
        ),
      ),
    );
  }

  Widget _mainActionButton() {
    return GestureDetector(
      onTap: _isSending
          ? null
          : (_isStreaming ? _stopLiveStream : _startLiveStream),
      child: Container(
        height: 70,
        width: 70,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(
              color: _isStreaming ? Colors.redAccent : Colors.cyanAccent,
              width: 2),
        ),
        child: Icon(
          _isStreaming ? Icons.stop : Icons.sensors,
          color: _isStreaming ? Colors.redAccent : Colors.cyanAccent,
          size: 35,
        ),
      ),
    );
  }

  Widget _hudButton(IconData icon, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white70),
          const SizedBox(height: 4),
          Text(label,
              style: const TextStyle(color: Colors.white54, fontSize: 10)),
        ],
      ),
    );
  }

  // ---------------- HELPERS ----------------
  void _startLiveStream() {
    setState(() {
      _isStreaming = true;
      _statusMessage = "LIVE FEED ACTIVE";
      _statusColor = Colors.greenAccent;
    });

    _scanController.repeat(reverse: true);

    _frameTimer =
        Timer.periodic(const Duration(milliseconds: 1200), (_) async {
      if (!_controller!.value.isInitialized || _isSending) return;
      final XFile file = await _controller!.takePicture();
      _sendData(File(file.path), BACKEND_IMAGE_URL, false);
    });
  }

  void _stopLiveStream() {
    _frameTimer?.cancel();
    _scanController.stop();

    setState(() {
      _isStreaming = false;
      _statusMessage = "SYSTEM IDLE";
      _statusColor = Colors.cyanAccent;
    });
  }

  Future<void> _pickFile({required bool isVideo}) async {
    final picker = ImagePicker();
    final XFile? file = isVideo
        ? await picker.pickVideo(source: ImageSource.gallery)
        : await picker.pickImage(source: ImageSource.gallery);

    if (file != null) {
      if (isVideo) {
        _uploadVideo(File(file.path));
      } else {
        _sendImage(File(file.path));
      }
    }
  }

  Future<void> _sendImage(File imageFile) async {
    await _sendData(imageFile, BACKEND_IMAGE_URL, false);
  }

  Future<void> _uploadVideo(File videoFile) async {
    if (_isSending) return;

    setState(() {
      _isSending = true;
      _statusMessage = "UPLOADING VIDEO...";
      _statusColor = Colors.orangeAccent;
    });

    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse(BACKEND_VIDEO_URL),
      );

      request.files.add(
        await http.MultipartFile.fromPath('file', videoFile.path),
      );

      final response = await request.send();

      setState(() {
        if (response.statusCode == 200) {
          _statusMessage = "VIDEO UPLOADED";
          _statusColor = Colors.greenAccent;
        } else {
          _statusMessage = "VIDEO UPLOAD FAILED";
          _statusColor = Colors.redAccent;
        }
      });
    } catch (e) {
      setState(() {
        _statusMessage = "CONNECTION ERROR";
        _statusColor = Colors.redAccent;
      });
    } finally {
      _isSending = false;
    }
  }
}

// --- TELEMETRY OVERLAY CLASS ---
class TelemetryOverlay extends StatefulWidget {
  const TelemetryOverlay({super.key});

  @override
  State<TelemetryOverlay> createState() => _TelemetryOverlayState();
}

class _TelemetryOverlayState extends State<TelemetryOverlay> {
  Timer? _telemetryTimer;
  double _alt = 120.5;
  double _speed = 45.2;
  final int _sat = 12;

  @override
  void initState() {
    super.initState();
    // Simulate real-time data shifting
    _telemetryTimer = Timer.periodic(const Duration(milliseconds: 800), (timer) {
      if (mounted) {
        setState(() {
          _alt += (DateTime.now().millisecond % 5 - 2) * 0.1;
          _speed += (DateTime.now().millisecond % 3 - 1) * 0.05;
        });
      }
    });
  }

  @override
  void dispose() {
    _telemetryTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const textStyle = TextStyle(
      color: Colors.cyanAccent,
      fontFamily: 'Courier', // Use a monospace font if available
      fontSize: 10,
      fontWeight: FontWeight.bold,
      letterSpacing: 1,
    );

    return Stack(
      children: [
        // Left Side Telemetry
        Positioned(
          left: 20,
          top: MediaQuery.of(context).size.height * 0.3,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _dataLine("ALT", "${_alt.toStringAsFixed(1)}m"),
              _dataLine("SPD", "${_speed.toStringAsFixed(1)}km/h"),
              _dataLine("LAT", "10.9382° N"),
              _dataLine("LNG", "75.9231° E"),
            ],
          ),
        ),
        // Right Side Telemetry
        Positioned(
          right: 20,
          top: MediaQuery.of(context).size.height * 0.3,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              _dataLine("SAT", "$_sat"),
              _dataLine("SIG", "||||| 98%"),
              _dataLine("BAT", "84%"),
              _dataLine("MODE", "AI_SCAN"),
            ],
          ),
        ),
        // Central Crosshair
        Center(
          child: Opacity(
            opacity: 0.3,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.cyanAccent, width: 0.5),
              ),
              child: Stack(
                children: [
                  Center(child: Container(width: 10, height: 1, color: Colors.cyanAccent)),
                  Center(child: Container(width: 1, height: 10, color: Colors.cyanAccent)),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _dataLine(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text("$label: ", style: const TextStyle(color: Colors.white38, fontSize: 9)),
          Text(value, style: const TextStyle(color: Colors.cyanAccent, fontSize: 10, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
