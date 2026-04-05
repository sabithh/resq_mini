// services/api_service.dart
// Centralised HTTP API calls. Reads backend URL from SharedPreferences.

import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String _keyBaseUrl = 'backend_base_url';
  static const String _defaultUrl = 'http://192.168.1.2:8000';

  // ── URL management ──────────────────────────────────

  /// Returns true if the user has explicitly saved a backend URL.
  /// Used by SplashScreen to decide whether to show the setup dialog.
  static Future<bool> hasCustomUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey(_keyBaseUrl);
  }

  static Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_keyBaseUrl) ?? _defaultUrl;
  }

  static Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyBaseUrl, url.trimRight().replaceAll(RegExp(r'/$'), ''));
  }

  // ── Detection ────────────────────────────────────────
  static Future<http.Response> sendImageForDetect(
    File imageFile, {
    String droneId = 'DRONE_1',
  }) async {
    final base = await getBaseUrl();
    final url  = Uri.parse('$base/detect');
    final req  = http.MultipartRequest('POST', url);
    req.fields['drone_id'] = droneId;
    req.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
    final streamed = await req.send().timeout(const Duration(seconds: 10));
    return http.Response.fromStream(streamed);
  }

  static Future<http.Response> sendImageForThermal(
    File imageFile, {
    String mode     = 'clahe',
    String droneId  = 'DRONE_1',
  }) async {
    final base = await getBaseUrl();
    final url  = Uri.parse('$base/detect-thermal');
    final req  = http.MultipartRequest('POST', url);
    req.fields['mode'] = mode;
    req.fields['drone_id'] = droneId;
    req.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
    final streamed = await req.send().timeout(const Duration(seconds: 10));
    return http.Response.fromStream(streamed);
  }

  static Future<http.Response> uploadVideo(File videoFile) async {
    final base = await getBaseUrl();
    final url  = Uri.parse('$base/upload-video');
    final req  = http.MultipartRequest('POST', url);
    req.files.add(await http.MultipartFile.fromPath('file', videoFile.path));
    final streamed = await req.send().timeout(const Duration(seconds: 10));
    return http.Response.fromStream(streamed);
  }

  // ── Stream controls ──────────────────────────────────
  static Future<bool> post(String path) async {
    try {
      final base = await getBaseUrl();
      final res  = await http.post(Uri.parse('$base$path')).timeout(
        const Duration(seconds: 5),
      );
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Status / ping ────────────────────────────────────
  static Future<bool> testConnection() async {
    try {
      final base = await getBaseUrl();
      final res  = await http.get(Uri.parse('$base/status')).timeout(
        const Duration(seconds: 4),
      );
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
