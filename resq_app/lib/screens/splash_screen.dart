// screens/splash_screen.dart

import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
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

    // After 2.5s: check if URL is configured, then route accordingly
    Timer(const Duration(milliseconds: 2500), _checkAndRoute);
  }

  Future<void> _checkAndRoute() async {
    if (!mounted) return;
    final hasUrl = await ApiService.hasCustomUrl();
    if (!mounted) return;

    if (hasUrl) {
      _goToApp();
    } else {
      // First launch — show IP setup sheet
      await _showSetupSheet();
    }
  }

  void _goToApp() {
    Navigator.of(context).pushReplacement(PageRouteBuilder(
      pageBuilder: (_, __, ___) => const CameraHome(),
      transitionsBuilder: (_, anim, __, child) =>
          FadeTransition(opacity: anim, child: child),
      transitionDuration: const Duration(milliseconds: 800),
    ));
  }

  Future<void> _showSetupSheet() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      isDismissible: false,      // must configure before entering
      enableDrag: false,
      backgroundColor: Colors.transparent,
      builder: (_) => const _SetupSheet(),
    );
    if (mounted) _goToApp();
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
                          color: Colors.cyanAccent.withValues(alpha: 0.3),
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
                      color: Colors.cyanAccent.withValues(alpha: 0.6),
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

// ── IP Setup Bottom Sheet ───────────────────────────────────────────────────

class _SetupSheet extends StatefulWidget {
  const _SetupSheet();
  @override
  State<_SetupSheet> createState() => _SetupSheetState();
}

class _SetupSheetState extends State<_SetupSheet> {
  final _ipCtrl = TextEditingController();
  final _portCtrl = TextEditingController(text: '8000');
  bool _testing = false;
  bool _connected = false;
  String _statusMsg = '';
  Color _statusColor = Colors.white54;

  @override
  void dispose() {
    _ipCtrl.dispose();
    _portCtrl.dispose();
    super.dispose();
  }

  String get _builtUrl {
    final ip = _ipCtrl.text.trim();
    final port = _portCtrl.text.trim();
    if (ip.isEmpty) return '';
    return 'http://$ip:$port';
  }

  Future<void> _testAndConnect() async {
    final url = _builtUrl;
    if (url.isEmpty) {
      setState(() {
        _statusMsg   = 'Please enter an IP address';
        _statusColor = Colors.orangeAccent;
      });
      return;
    }

    setState(() {
      _testing     = true;
      _connected   = false;
      _statusMsg   = 'CONNECTING TO $url...';
      _statusColor = Colors.orangeAccent;
    });

    // Save first so ApiService uses this URL for testConnection()
    await ApiService.setBaseUrl(url);
    final ok = await ApiService.testConnection();

    if (!mounted) return;
    setState(() {
      _testing     = false;
      _connected   = ok;
      _statusMsg   = ok ? '✔ CONNECTED — TAP LAUNCH TO PROCEED' : '✘ NO RESPONSE — CHECK IP AND PORT';
      _statusColor = ok ? Colors.greenAccent : Colors.redAccent;
    });
  }

  Future<void> _skip() async {
    // Save whatever is typed (or empty → will use default) and continue
    final url = _builtUrl;
    if (url.isNotEmpty) await ApiService.setBaseUrl(url);
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12),
      padding: EdgeInsets.fromLTRB(24, 28, 24, 28 + bottom),
      decoration: BoxDecoration(
        color: const Color(0xFF080F1A),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        border: Border.all(color: Colors.cyanAccent.withValues(alpha: 0.25)),
        boxShadow: [
          BoxShadow(
            color: Colors.cyanAccent.withValues(alpha: 0.08),
            blurRadius: 30, spreadRadius: -5,
          ),
        ],
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ──────────────────────────────────────
            Row(children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.cyanAccent.withValues(alpha: 0.1),
                  border: Border.all(color: Colors.cyanAccent.withValues(alpha: 0.4)),
                ),
                child: const Icon(Icons.wifi_find_rounded, color: Colors.cyanAccent, size: 20),
              ),
              const SizedBox(width: 14),
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('BACKEND SETUP',
                    style: TextStyle(
                        color: Colors.white, fontSize: 16,
                        fontWeight: FontWeight.bold, letterSpacing: 4)),
                Text('ENTER YOUR DRONE CONTROLLER IP',
                    style: TextStyle(
                        color: Colors.cyanAccent.withValues(alpha: 0.5),
                        fontSize: 9, letterSpacing: 2)),
              ]),
            ]),

            const SizedBox(height: 28),

            // ── Labels ──────────────────────────────────────
            Row(children: [
              Expanded(
                flex: 3,
                child: _label('IP ADDRESS'),
              ),
              const SizedBox(width: 12),
              SizedBox(width: 90, child: _label('PORT')),
            ]),
            const SizedBox(height: 6),

            // ── Input Row ────────────────────────────────────
            Row(children: [
              Expanded(
                flex: 3,
                child: _inputBox(
                  controller: _ipCtrl,
                  hint: '192.168.1.100',
                  keyboard: TextInputType.number,
                  icon: Icons.router_rounded,
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 90,
                child: _inputBox(
                  controller: _portCtrl,
                  hint: '8000',
                  keyboard: TextInputType.number,
                  icon: Icons.electrical_services_rounded,
                ),
              ),
            ]),

            const SizedBox(height: 10),

            // Preview URL
            if (_ipCtrl.text.isNotEmpty || _portCtrl.text.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Text(
                  'URL: $_builtUrl',
                  style: TextStyle(
                      color: Colors.cyanAccent.withValues(alpha: 0.45),
                      fontSize: 10, letterSpacing: 1),
                ),
              ),

            // ── Status msg ───────────────────────────────────
            if (_statusMsg.isNotEmpty) ...[
              const SizedBox(height: 6),
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: _statusColor.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: _statusColor.withValues(alpha: 0.3)),
                ),
                child: Text(_statusMsg,
                    style: TextStyle(color: _statusColor, fontSize: 10, letterSpacing: 1)),
              ),
            ],

            const SizedBox(height: 20),

            // ── Buttons ──────────────────────────────────────
            if (_connected)
              // LAUNCH — only show after successful connection
              _bigBtn(
                label: '🚀 LAUNCH RESQ',
                bg: Colors.cyanAccent,
                fg: Colors.black,
                onTap: () => Navigator.of(context).pop(),
              )
            else
              _bigBtn(
                label: _testing ? 'CONNECTING...' : '⚡ CONNECT & TEST',
                bg: Colors.cyanAccent,
                fg: Colors.black,
                onTap: _testing ? null : _testAndConnect,
              ),

            const SizedBox(height: 10),
            _bigBtn(
              label: 'SKIP FOR NOW',
              bg: Colors.transparent,
              fg: Colors.white38,
              onTap: _testing ? null : _skip,
              border: Colors.white12,
            ),

            const SizedBox(height: 6),
            Center(
              child: Text(
                'You can always change this in Settings',
                style: TextStyle(
                    color: Colors.white24, fontSize: 9, letterSpacing: 1),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _label(String text) => Text(text,
      style: TextStyle(
          color: Colors.cyanAccent.withValues(alpha: 0.55),
          fontSize: 9, letterSpacing: 3));

  Widget _inputBox({
    required TextEditingController controller,
    required String hint,
    required TextInputType keyboard,
    required IconData icon,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.cyanAccent.withValues(alpha: 0.25)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: TextField(
        controller: controller,
        keyboardType: keyboard,
        style: const TextStyle(color: Colors.white, fontSize: 14, letterSpacing: 1),
        onChanged: (_) => setState(() {}), // rebuild preview URL
        decoration: InputDecoration(
          border: InputBorder.none,
          hintText: hint,
          hintStyle: const TextStyle(color: Colors.white24, fontSize: 13),
          isDense: true,
          prefixIcon: Icon(icon, color: Colors.cyanAccent.withValues(alpha: 0.45), size: 16),
          prefixIconConstraints: const BoxConstraints(minWidth: 32, minHeight: 32),
          contentPadding: const EdgeInsets.symmetric(vertical: 12),
        ),
      ),
    );
  }

  Widget _bigBtn({
    required String label,
    required Color bg,
    required Color fg,
    VoidCallback? onTap,
    Color? border,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedOpacity(
        opacity: onTap == null ? 0.4 : 1.0,
        duration: const Duration(milliseconds: 200),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 15),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(12),
            border: border != null ? Border.all(color: border) : null,
            boxShadow: bg == Colors.cyanAccent
                ? [BoxShadow(color: Colors.cyanAccent.withValues(alpha: 0.25), blurRadius: 16, spreadRadius: -4)]
                : null,
          ),
          alignment: Alignment.center,
          child: Text(label,
              style: TextStyle(
                  color: fg, fontSize: 13,
                  fontWeight: FontWeight.bold, letterSpacing: 3)),
        ),
      ),
    );
  }
}

// ── Grid Background Painter ─────────────────────────────────────────────────

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
