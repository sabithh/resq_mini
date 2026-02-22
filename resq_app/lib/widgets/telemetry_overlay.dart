// widgets/telemetry_overlay.dart

import 'dart:async';
import 'package:flutter/material.dart';

class TelemetryOverlay extends StatefulWidget {
  const TelemetryOverlay({super.key});
  @override
  State<TelemetryOverlay> createState() => _TelemetryOverlayState();
}

class _TelemetryOverlayState extends State<TelemetryOverlay> {
  Timer? _timer;
  double _alt   = 120.5;
  double _speed = 45.2;
  final int _sat = 12;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 800), (_) {
      if (mounted) {
        setState(() {
          _alt   += (DateTime.now().millisecond % 5 - 2) * 0.1;
          _speed += (DateTime.now().millisecond % 3 - 1) * 0.05;
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Widget _dataLine(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label: ', style: const TextStyle(color: Colors.white38, fontSize: 9)),
        Text(value,
            style: const TextStyle(
                color: Colors.cyanAccent, fontSize: 10, fontWeight: FontWeight.bold)),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      // Left telemetry
      Positioned(
        left: 20,
        top: MediaQuery.of(context).size.height * 0.3,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _dataLine('ALT',  '${_alt.toStringAsFixed(1)}m'),
          _dataLine('SPD',  '${_speed.toStringAsFixed(1)}km/h'),
          _dataLine('LAT',  '10.9382° N'),
          _dataLine('LNG',  '75.9231° E'),
        ]),
      ),
      // Right telemetry
      Positioned(
        right: 20,
        top: MediaQuery.of(context).size.height * 0.3,
        child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          _dataLine('SAT',  '$_sat'),
          _dataLine('SIG',  '||||| 98%'),
          _dataLine('BAT',  '84%'),
          _dataLine('MODE', 'AI_SCAN'),
        ]),
      ),
      // Crosshair
      Center(
        child: Opacity(
          opacity: 0.3,
          child: Container(
            width: 100, height: 100,
            decoration: BoxDecoration(
                border: Border.all(color: Colors.cyanAccent, width: 0.5)),
            child: Stack(children: [
              Center(child: Container(width: 10, height: 1, color: Colors.cyanAccent)),
              Center(child: Container(width: 1, height: 10, color: Colors.cyanAccent)),
            ]),
          ),
        ),
      ),
    ]);
  }
}
