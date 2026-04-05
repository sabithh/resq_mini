// main.dart — ResQ App v2
// Thin entry point: sets up cameras and routes to SplashScreen

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';

import 'screens/splash_screen.dart';
import 'screens/camera_home.dart';   // exposes cameras

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  cameras = await availableCameras();
  runApp(const ResQApp());
}

class ResQApp extends StatelessWidget {
  const ResQApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ResQ',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.dark(
          primary:   Colors.cyanAccent,
          secondary: Colors.cyanAccent,
          surface:   Colors.black,
        ),
        scaffoldBackgroundColor: Colors.black,
        fontFamily: 'monospace',
      ),
      home: const SplashScreen(),
    );
  }
}
