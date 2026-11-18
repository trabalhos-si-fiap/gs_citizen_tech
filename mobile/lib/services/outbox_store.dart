import 'dart:convert';
import 'dart:io';

import 'package:shared_preferences/shared_preferences.dart';

class OutboxStore {
  static const _key = 'reclame_ja_report_outbox';

  static Future<List<Map<String, dynamic>>> load() async {
    final preferences = await SharedPreferences.getInstance();
    final rawItems = preferences.getStringList(_key) ?? <String>[];
    return rawItems
        .map((item) => jsonDecode(item) as Map<String, dynamic>)
        .toList();
  }

  static Future<void> enqueue(Map<String, dynamic> payload) async {
    final preferences = await SharedPreferences.getInstance();
    final items = preferences.getStringList(_key) ?? <String>[];
    final index = items.indexWhere((item) {
      final existing = jsonDecode(item) as Map<String, dynamic>;
      return existing['id'] == payload['id'];
    });
    if (index == -1) {
      items.add(jsonEncode(payload));
    } else {
      items[index] = jsonEncode(payload);
    }
    await preferences.setStringList(_key, items);
  }

  static Future<void> remove(String reportId) async {
    final preferences = await SharedPreferences.getInstance();
    final items = preferences.getStringList(_key) ?? <String>[];
    String? photoPath;
    items.removeWhere((item) {
      final payload = jsonDecode(item) as Map<String, dynamic>;
      if (payload['id'] != reportId) return false;
      photoPath = payload['photo_path'] as String?;
      return true;
    });
    await preferences.setStringList(_key, items);
    if (photoPath != null) {
      final photoFile = File(photoPath!);
      if (await photoFile.exists()) await photoFile.delete();
    }
  }
}
