import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SessionStore {
  static const _storage = FlutterSecureStorage();
  static const _accessKey = 'reclame_ja_access_token';
  static const _refreshKey = 'reclame_ja_refresh_token';
  static const _emailKey = 'reclame_ja_account_email';
  static const _nameKey = 'reclame_ja_display_name';
  static String? accessToken;
  static String? refreshToken;
  static String? accountEmail;
  static String? displayName;

  static Future<void> restore() async {
    accessToken = await _storage.read(key: _accessKey);
    refreshToken = await _storage.read(key: _refreshKey);
    accountEmail = await _storage.read(key: _emailKey);
    // Sessões salvas antes de o nome ser guardado: usa o usuário do e-mail.
    displayName = await _storage.read(key: _nameKey) ??
        (accountEmail == null ? null : displayNameFromEmail(accountEmail!));
  }

  /// Nome da saudação ("Olá, ana.cidada"): o usuário do e-mail, antes do @.
  static String displayNameFromEmail(String email) => email.split('@').first;

  static Future<void> saveTokens(
      String accessToken, String refreshToken) async {
    SessionStore.accessToken = accessToken;
    SessionStore.refreshToken = refreshToken;
    await _storage.write(key: _accessKey, value: accessToken);
    await _storage.write(key: _refreshKey, value: refreshToken);
  }

  static Future<void> saveAccountEmail(String email) async {
    accountEmail = email;
    await _storage.write(key: _emailKey, value: email);
  }

  static Future<void> saveDisplayName(String name) async {
    displayName = name;
    await _storage.write(key: _nameKey, value: name);
  }

  static Future<void> clear() async {
    accessToken = null;
    refreshToken = null;
    accountEmail = null;
    displayName = null;
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
    await _storage.delete(key: _emailKey);
    await _storage.delete(key: _nameKey);
  }
}
