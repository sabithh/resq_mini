import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

/// CHANGE THIS TO YOUR LAPTOP IP
const String BACKEND_URL = "http://192.168.1.8:8000/detect";

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
      title: 'ResQ Drone Client',
      theme: ThemeData.dark(),
      home: const CameraHome(),
    );
  }
}

class CameraHome extends StatefulWidget {
  const CameraHome({super.key});

  @override
  State<CameraHome> createState() => _CameraHomeState();
}

class _CameraHomeState extends State<CameraHome> {
  CameraController? _controller;
  bool _isStreaming = false;
  bool _isSending = false;
  Timer? _frameTimer;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    _controller = CameraController(
      cameras.first,
      ResolutionPreset.medium, // IMPORTANT: CPU SAFE
      enableAudio: false,
    );
    await _controller!.initialize();
    setState(() {});
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  // --------------------------------------------
  // SEND IMAGE TO BACKEND
  // --------------------------------------------
  Future<void> _sendImage(File imageFile) async {
    if (_isSending) return;

    _isSending = true;

    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse(BACKEND_URL),
      );

      request.files.add(
        await http.MultipartFile.fromPath('file', imageFile.path),
      );

      await request.send();
    } catch (e) {
      debugPrint("Upload error: $e");
    } finally {
      _isSending = false;
    }
  }

  // --------------------------------------------
  // LIVE STREAM (OPTION A)
  // --------------------------------------------
  void _startLiveStream() {
    if (_isStreaming) return;

    _isStreaming = true;

    _frameTimer = Timer.periodic(const Duration(milliseconds: 500), (_) async {
      if (!_controller!.value.isInitialized) return;

      final XFile file = await _controller!.takePicture();
      _sendImage(File(file.path));
    });

    setState(() {});
  }

  void _stopLiveStream() {
    _frameTimer?.cancel();
    _isStreaming = false;
    setState(() {});
  }

  // --------------------------------------------
  // GALLERY UPLOAD
  // --------------------------------------------
  Future<void> _pickFromGallery() async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.gallery);

    if (image != null) {
      _sendImage(File(image.path));
    }
  }

  // --------------------------------------------
  // UI
  // --------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("ResQ Drone – Camera Unit"),
        centerTitle: true,
      ),
      body: Column(
        children: [
          Expanded(
            child: _controller == null || !_controller!.value.isInitialized
                ? const Center(child: CircularProgressIndicator())
                : CameraPreview(_controller!),
          ),

          const SizedBox(height: 10),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              ElevatedButton.icon(
                icon: const Icon(Icons.camera),
                label: Text(_isStreaming ? "STOP LIVE" : "START LIVE"),
                style: ElevatedButton.styleFrom(
                  backgroundColor:
                      _isStreaming ? Colors.red : Colors.green,
                ),
                onPressed:
                    _isStreaming ? _stopLiveStream : _startLiveStream,
              ),

              ElevatedButton.icon(
                icon: const Icon(Icons.photo),
                label: const Text("Gallery"),
                onPressed: _pickFromGallery,
              ),
            ],
          ),

          const SizedBox(height: 15),

          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Text(
              _isStreaming
                  ? "📡 Live feed sending to Control Room..."
                  : "🛑 Live feed stopped",
              style: const TextStyle(color: Colors.orange),
            ),
          ),
        ],
      ),
    );
  }
}
