// screens/settings_screen.dart

import 'package:flutter/material.dart';
import 'dart:ui';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlCtrl = TextEditingController();
  String _status = '';
  Color  _statusColor = Colors.cyanAccent;
  bool   _testing = false;

  @override
  void initState() {
    super.initState();
    ApiService.getBaseUrl().then((url) => _urlCtrl.text = url);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await ApiService.setBaseUrl(_urlCtrl.text.trim());
    setState(() {
      _status      = 'URL SAVED';
      _statusColor = Colors.greenAccent;
    });
  }

  Future<void> _test() async {
    setState(() { _testing = true; _status = 'TESTING CONNECTION...'; _statusColor = Colors.orangeAccent; });
    final ok = await ApiService.testConnection();
    setState(() {
      _testing     = false;
      _status      = ok ? '✔ CONNECTED' : '✘ NO RESPONSE';
      _statusColor = ok ? Colors.greenAccent : Colors.redAccent;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.cyanAccent,
        title: const Text('SETTINGS',
            style: TextStyle(letterSpacing: 6, fontSize: 14, color: Colors.cyanAccent)),
        centerTitle: true,
        elevation: 0,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(height: 1, color: Colors.cyanAccent.withValues(alpha: 0.2)),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [

          // ── Backend URL ──────────────────────────────────
          _sectionLabel('BACKEND URL'),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.cyanAccent.withValues(alpha: 0.3)),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: TextField(
                  controller: _urlCtrl,
                  style: const TextStyle(color: Colors.white, fontSize: 13, letterSpacing: 1),
                  decoration: InputDecoration(
                    border: InputBorder.none,
                    hintText: 'http://192.168.1.2:8000',
                    hintStyle: TextStyle(color: Colors.white24, fontSize: 12),
                    prefixIcon: Icon(Icons.link, color: Colors.cyanAccent.withValues(alpha: 0.5), size: 18),
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 12),

          // Buttons
          Row(children: [
            Expanded(child: _actionBtn('💾 SAVE', Colors.cyanAccent, Colors.black, _save)),
            const SizedBox(width: 10),
            Expanded(child: _actionBtn(
              _testing ? 'TESTING...' : '⚡ TEST',
              Colors.transparent, Colors.cyanAccent, _testing ? null : _test,
              border: Colors.cyanAccent,
            )),
          ]),

          // Status
          if (_status.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(_status, style: TextStyle(color: _statusColor, fontSize: 11, letterSpacing: 2)),
          ],

          const SizedBox(height: 32),

          // ── Info ─────────────────────────────────────────
          _sectionLabel('INFO'),
          const SizedBox(height: 10),
          _infoRow('APP VERSION', 'ResQ v2.0'),
          _infoRow('DETECTION', 'YOLOv8m + ByteTrack'),
          _infoRow('THERMAL MODE', 'CLAHE / False-Color / Raw'),
          _infoRow('DASHBOARDS', '/dashboard · /dashboard/thermal · /dashboard/video'),

          const SizedBox(height: 32),

          // ── Dashboards quick-links ────────────────────────
          _sectionLabel('QUICK LINKS'),
          const SizedBox(height: 10),
          _linkHint('Main Dashboard',    '/dashboard'),
          _linkHint('Thermal Lab',       '/dashboard/thermal'),
          _linkHint('Video Control',     '/dashboard/video'),
          _linkHint('API Docs',          '/docs'),
        ]),
      ),
    );
  }

  Widget _sectionLabel(String text) => Text(text,
    style: TextStyle(color: Colors.cyanAccent.withValues(alpha: 0.6),
        fontSize: 10, letterSpacing: 4, fontWeight: FontWeight.bold));

  Widget _actionBtn(String label, Color bg, Color fg, VoidCallback? onTap,
      {Color? border}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(10),
          border: border != null ? Border.all(color: border) : null,
        ),
        alignment: Alignment.center,
        child: Text(label, style: TextStyle(
            color: fg, fontSize: 12,
            fontWeight: FontWeight.bold, letterSpacing: 2)),
      ),
    );
  }

  Widget _infoRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Row(children: [
      SizedBox(width: 140, child: Text(label,
          style: const TextStyle(color: Colors.white38, fontSize: 10, letterSpacing: 1))),
      Expanded(child: Text(value,
          style: const TextStyle(color: Colors.white70, fontSize: 10))),
    ]),
  );

  Widget _linkHint(String label, String path) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(children: [
      const Icon(Icons.link, color: Colors.cyanAccent, size: 14),
      const SizedBox(width: 8),
      Text(label, style: const TextStyle(color: Colors.white60, fontSize: 11)),
      const Spacer(),
      Text(path, style: const TextStyle(color: Colors.cyanAccent, fontSize: 10)),
    ]),
  );
}
