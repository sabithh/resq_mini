// screens/splash_screen.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'camera_home.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat(reverse: true);
    _pulse = Tween<double>(begin: 1.0, end: 1.2)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));

    Timer(const Duration(milliseconds: 3500), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(PageRouteBuilder(
          pageBuilder: (_, __, ___) => const CameraHome(),
          transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
          transitionDuration: const Duration(milliseconds: 1000),
        ));
      }
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(children: [
        Opacity(
          opacity: 0.1,
          child: CustomPaint(
            size: MediaQuery.of(context).size,
            painter: _GridPainter(),
          ),
        ),
        Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ScaleTransition(
                scale: _pulse,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.cyanAccent, width: 2),
                    boxShadow: [
                      BoxShadow(
                          color: Colors.cyanAccent.withOpacity(0.3),
                          blurRadius: 20,
                          spreadRadius: 5)
                    ],
                  ),
                  child: const Icon(Icons.navigation_rounded,
                      size: 80, color: Colors.cyanAccent),
                ),
              ),
              const SizedBox(height: 40),
              const Text('RESQ_SYSTEMS',
                  style: TextStyle(
                      color: Colors.white, fontSize: 24,
                      fontWeight: FontWeight.bold, letterSpacing: 8)),
              const SizedBox(height: 10),
              Text('ESTABLISHING SECURE LINK...',
                  style: TextStyle(
                      color: Colors.cyanAccent.withOpacity(0.6),
                      fontSize: 10, letterSpacing: 2)),
              const SizedBox(height: 50),
              SizedBox(
                width: 200,
                child: Column(children: [
                  const LinearProgressIndicator(
                      backgroundColor: Colors.white10,
                      color: Colors.cyanAccent, minHeight: 2),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: const [
                      Text('V_4.02',
                          style: TextStyle(color: Colors.white24, fontSize: 8)),
                      Text('RUNNING_DIAGNOSTICS',
                          style: TextStyle(color: Colors.white24, fontSize: 8)),
                    ],
                  )
                ]),
              ),
            ],
          ),
        ),
      ]),
    );
  }
}

class _GridPainter extends CustomPainter {
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
  bool shouldRepaint(CustomPainter _) => false;
}
