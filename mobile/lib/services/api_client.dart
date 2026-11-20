import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:crypto/crypto.dart' as crypto;

import 'outbox_store.dart';
import 'session_store.dart';

/// Tamanho máximo de `address` aceito por `POST /v1/reports`.
const maxAddressLength = 200;

class ApiConfig {
  static String baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
}

class OutboxSyncResult {
  const OutboxSyncResult({required this.synced, this.error});

  final int synced;
  final Object? error;

  bool get hasPendingFailure => error != null;
}

/// O munícipe já sinalizou esse reporte antes (409 em `/flag`).
class ReportAlreadyFlaggedException implements Exception {
  const ReportAlreadyFlaggedException();
}

/// A ação exige login e a API recusou a sessão (401), mesmo após renovar.
class SignInRequiredException implements Exception {
  const SignInRequiredException();
}

class ApiClient {
  static Future<bool>? _refreshInProgress;

  Map<String, String> get _headers => {
        'Accept': 'application/json',
        if (SessionStore.accessToken != null)
          'Authorization': 'Bearer ${SessionStore.accessToken}',
      };

  Future<http.Response> _authorized(
    Future<http.Response> Function(Map<String, String> headers) send,
  ) async {
    var response = await send(_headers);
    if (response.statusCode == 401 &&
        SessionStore.refreshToken != null &&
        await refreshSession()) {
      response = await send(_headers);
    }
    return response;
  }

  Future<void> requestOtp({
    required String email,
    required String consentVersion,
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/v1/auth/login'),
      headers: {..._headers, 'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'consent': {
          'version': consentVersion,
          'accepted_age': true,
        },
      }),
    );
    if (response.statusCode != 202) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<Map<String, dynamic>> verifyOtp({
    required String email,
    required String code,
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/v1/auth/login'),
      headers: {..._headers, 'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'code': code,
      }),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    final data =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    final accessToken = data['access_token'] as String?;
    final refreshToken = data['refresh_token'] as String?;
    if (accessToken != null && refreshToken != null) {
      await SessionStore.saveTokens(accessToken, refreshToken);
    }
    return data;
  }

  Future<bool> refreshSession() {
    final inProgress = _refreshInProgress;
    if (inProgress != null) return inProgress;
    final refresh = _refreshSession();
    _refreshInProgress = refresh;
    return refresh.whenComplete(() => _refreshInProgress = null);
  }

  Future<bool> _refreshSession() async {
    final refreshToken = SessionStore.refreshToken;
    if (refreshToken == null) return false;
    final response = await http.post(
      Uri.parse('${ApiConfig.baseUrl}/v1/auth/refresh'),
      headers: const {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: jsonEncode({'refresh_token': refreshToken}),
    );
    if (response.statusCode != 200) return false;
    final data =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    final accessToken = data['access_token'] as String?;
    final rotatedRefreshToken = data['refresh_token'] as String?;
    if (accessToken == null || rotatedRefreshToken == null) return false;
    await SessionStore.saveTokens(accessToken, rotatedRefreshToken);
    return true;
  }

  Future<Map<String, dynamic>> createReport({
    required String id,
    required String description,
    required double lat,
    required double lon,
    double? locationAccuracyM,
    required bool anonymous,
    String? category,
    bool hasPhoto = false,
    String? clientCreatedAt,
    String? address,
  }) async {
    final trimmedAddress = address?.trim() ?? '';
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'id': id,
          'description': description,
          'has_photo': hasPhoto,
          // Sem categoria escolhida, a IA classifica sem palpite do app.
          if (category != null) 'category': category,
          'lat': lat,
          'lon': lon,
          if (locationAccuracyM != null)
            'location_accuracy_m': locationAccuracyM,
          'anonymous': anonymous,
          if (trimmedAddress.isNotEmpty)
            'address': trimmedAddress.length > maxAddressLength
                ? trimmedAddress.substring(0, maxAddressLength)
                : trimmedAddress,
          'client_created_at':
              clientCreatedAt ?? DateTime.now().toUtc().toIso8601String(),
        }),
      ),
    );
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<OutboxSyncResult> flushOutbox() async {
    final pending = await OutboxStore.load();
    var synced = 0;
    for (final item in pending) {
      try {
        final id = item['id'] as String;
        final hasPhoto = item['has_photo'] as bool? ?? false;
        final created = await createReport(
          id: id,
          description: item['description'] as String? ?? '',
          lat: (item['lat'] as num).toDouble(),
          lon: (item['lon'] as num).toDouble(),
          locationAccuracyM: (item['location_accuracy_m'] as num?)?.toDouble(),
          anonymous: item['anonymous'] as bool? ?? false,
          category: item['category'] as String?,
          hasPhoto: hasPhoto,
          clientCreatedAt: item['client_created_at'] as String,
          address: item['address'] as String?,
        );
        if (hasPhoto) {
          final photoPath = item['photo_path'] as String?;
          final upload = created['upload'] as Map<String, dynamic>?;
          if (photoPath == null || upload == null) {
            throw StateError('Não foi possível retomar o envio da foto.');
          }
          final file = File(photoPath);
          if (!await file.exists()) {
            throw StateError('A foto pendente não está mais disponível.');
          }
          await uploadPhoto(
            reportId: created['id'] as String,
            upload: upload,
            bytes: await file.readAsBytes(),
          );
        }
        await OutboxStore.remove(id);
        synced++;
      } on SocketException catch (error) {
        return OutboxSyncResult(synced: synced, error: error);
      } on http.ClientException catch (error) {
        return OutboxSyncResult(synced: synced, error: error);
      } on TimeoutException catch (error) {
        return OutboxSyncResult(synced: synced, error: error);
      } on StateError catch (error) {
        return OutboxSyncResult(synced: synced, error: error);
      }
    }
    return OutboxSyncResult(synced: synced);
  }

  Future<void> uploadPhoto({
    required String reportId,
    required Map<String, dynamic> upload,
    required Uint8List bytes,
  }) async {
    final uploadHeaders = <String, String>{
      'Content-Type': 'application/octet-stream',
    };
    if (upload['headers'] is Map) {
      for (final entry in (upload['headers'] as Map).entries) {
        uploadHeaders[entry.key.toString()] = entry.value.toString();
      }
    }
    final response = await http.put(
      Uri.parse(upload['url'] as String),
      headers: uploadHeaders,
      body: bytes,
    );
    if (response.statusCode != 204) {
      throw Exception(_errorMessage(response));
    }

    final digest = crypto.sha256.convert(bytes).toString();
    final completeResponse = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/photo/complete'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({'sha256': digest}),
      ),
    );
    if (completeResponse.statusCode != 202) {
      throw Exception(_errorMessage(completeResponse));
    }
  }

  Future<Map<String, dynamic>> getReport(String id) async {
    final response = await _authorized(
      (headers) => http.get(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$id'),
        headers: headers,
      ),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listMyReports() async {
    final response = await _authorized(
      (headers) => http.get(
        Uri.parse('${ApiConfig.baseUrl}/v1/me/reports'),
        headers: headers,
      ),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> triageReport({
    required String reportId,
    required String action,
    String? category,
    String? subcategory,
  }) async {
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/triage'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'action': action,
          if (category != null) 'category': category,
          if (subcategory != null) 'subcategory': subcategory,
        }),
      ),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getComments(String reportId) async {
    final response = await _authorized(
      (headers) => http.get(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/comments'),
        headers: headers,
      ),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> addComment({
    required String reportId,
    required String content,
  }) async {
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/comments'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({'content': content}),
      ),
    );
    if (response.statusCode != 201) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> confirmReport(String reportId) async {
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/confirm'),
        headers: headers,
      ),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  /// Sinaliza o reporte para a moderação. [reason]: ofensivo, dados_pessoais,
  /// falso, duplicado_abusivo ou outro.
  Future<void> flagReport({
    required String reportId,
    required String reason,
    String? note,
  }) async {
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/flag'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'reason': reason,
          if (note != null && note.isNotEmpty) 'note': note,
        }),
      ),
    );
    if (response.statusCode == 401) throw const SignInRequiredException();
    if (response.statusCode == 409) {
      throw const ReportAlreadyFlaggedException();
    }
    if (response.statusCode != 202) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<Map<String, dynamic>> reopenReport({
    required String reportId,
    String? reason,
  }) async {
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/reopen'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({if (reason != null) 'reason': reason}),
      ),
    );
    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<void> nudgeReport(String reportId) async {
    final response = await _authorized(
      (headers) => http.post(
        Uri.parse('${ApiConfig.baseUrl}/v1/reports/$reportId/nudge'),
        headers: headers,
      ),
    );
    if (response.statusCode != 202) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<void> registerDevice({
    required String pushToken,
    required String platform,
  }) async {
    final response = await _authorized(
      (headers) => http.put(
        Uri.parse('${ApiConfig.baseUrl}/v1/me/devices'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({'push_token': pushToken, 'platform': platform}),
      ),
    );
    if (response.statusCode != 204) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<void> removeDevice(String pushToken) async {
    final response = await _authorized(
      (headers) => http.delete(
        Uri.parse('${ApiConfig.baseUrl}/v1/me/devices'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'push_token': pushToken,
          'platform': defaultTargetPlatform == TargetPlatform.android
              ? 'android'
              : 'ios',
        }),
      ),
    );
    if (response.statusCode != 204) {
      throw Exception(_errorMessage(response));
    }
  }

  Future<Map<String, dynamic>> exportMyData() async {
    final response = await _authorized(
      (headers) => http.get(
        Uri.parse('${ApiConfig.baseUrl}/v1/me/export'),
        headers: headers,
      ),
    );
    if (response.statusCode != 200) {
      throw Exception('Falha ao exportar dados (${response.statusCode}).');
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  Future<void> deleteAccount() async {
    final response = await _authorized(
      (headers) => http.delete(
        Uri.parse('${ApiConfig.baseUrl}/v1/me'),
        headers: headers,
      ),
    );
    if (response.statusCode != 202) {
      throw Exception('Falha ao excluir conta (${response.statusCode}).');
    }
  }

  Future<Map<String, dynamic>> getPublicMetrics() async {
    final response = await http.get(
      Uri.parse('${ApiConfig.baseUrl}/v1/public/metrics'),
      headers: const {'Accept': 'application/json'},
    );
    if (response.statusCode != 200) {
      throw Exception('Falha ao consultar métricas (${response.statusCode}).');
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  String _errorMessage(http.Response response) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map<String, dynamic>) {
        final error = decoded['error'];
        if (error is Map<String, dynamic> && error['message'] is String) {
          return error['message'] as String;
        }
        if (decoded['detail'] is String) {
          return decoded['detail'] as String;
        }
      }
    } on FormatException {
      return 'Falha na comunicação com a API (${response.statusCode}).';
    }
    return 'Falha na comunicação com a API (${response.statusCode}).';
  }
}
