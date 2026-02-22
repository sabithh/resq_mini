// services/api_service.dart
// Centralised HTTP API calls. Reads backend URL from SharedPreferences.

import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String _keyBaseUrl = 'backend_base_url';
  static const String _defaultUrl = 'http://192.168.1.2:8000';

  // ── URL management ──────────────────────────────────
  static Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_keyBaseUrl) ?? _defaultUrl;
  }

  static Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyBaseUrl, url.trimRight().replaceAll(RegExp(r'/$'), ''));
  }

  // ── Detection ────────────────────────────────────────
  static Future<http.StreamedResponse> sendImageForDetect(
    File imageFile, {
    String droneId = 'DRONE_1',
  }) async {
    final base = await getBaseUrl();
    final url  = Uri.parse('$base/detect?drone_id=$droneId');
    final req  = http.MultipartRequest('POST', url);
    req.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
    return req.send();
  }

  static Future<http.StreamedResponse> sendImageForThermal(
    File imageFile, {
    String mode     = 'clahe',
    String droneId  = 'DRONE_1',
  }) async {
    final base = await getBaseUrl();
    final url  = Uri.parse('$base/detect-thermal?mode=$mode&drone_id=$droneId');
    final req  = http.MultipartRequest('POST', url);
    req.files.add(await http.MultipartFile.fromPath('file', imageFile.path));
    return req.send();
  }

  static Future<http.StreamedResponse> uploadVideo(File videoFile) async {
    final base = await getBaseUrl();
    final url  = Uri.parse('$base/upload-video');
    final req  = http.MultipartRequest('POST', url);
    req.files.add(await http.MultipartFile.fromPath('file', videoFile.path));
    return req.send();
  }

  // ── Stream controls ──────────────────────────────────
  static Future<bool> post(String path) async {
    try {
      final base = await getBaseUrl();
      final res  = await http.post(Uri.parse('$base$path'));
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
