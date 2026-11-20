import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'category_labels.dart';
import 'report_store.dart';

/// Rótulos dos chips de filtro e o valor correspondente na API.
const Map<String, String> _categoryByLabel = {
  'Risco Urbano': 'risco_urbano',
  'Transporte': 'transporte_publico',
  'Saúde': 'saude_atendimento',
};

/// Valor de `category` da API para o rótulo de um chip (`null` = todas).
String? categoryForLabel(String label) => _categoryByLabel[label];

String _statusLabel(String status) => switch (status) {
      'encaminhado' => 'Encaminhado',
      'em_andamento' => 'Em andamento',
      'resolvido' => 'Resolvido',
      _ => 'Recebido',
    };

/// Ocorrência pública devolvida por `GET /v1/reports/nearby`.
///
/// Não tem descrição, protocolo, foto nem autor: a API não publica esses dados.
class NearbyReport {
  const NearbyReport({
    required this.id,
    required this.groupId,
    required this.status,
    required this.category,
    required this.latitude,
    required this.longitude,
    required this.confirmationCount,
    required this.receivedAt,
    required this.distanceM,
  });

  factory NearbyReport.fromJson(Map<String, dynamic> json) => NearbyReport(
        id: json['id'].toString(),
        groupId: json['group_id']?.toString(),
        status: json['status']?.toString() ?? 'recebido',
        category: json['category']?.toString(),
        latitude: (json['lat'] as num).toDouble(),
        longitude: (json['lon'] as num).toDouble(),
        confirmationCount: (json['confirmation_count'] as num?)?.toInt() ?? 0,
        receivedAt: DateTime.tryParse(json['received_at']?.toString() ?? ''),
        distanceM: (json['distance_m'] as num?)?.round() ?? 0,
      );

  final String id;
  final String? groupId;
  final String status;
  final String? category;
  final double latitude;
  final double longitude;
  final int confirmationCount;
  final DateTime? receivedAt;
  final int distanceM;

  String get categoryLabel => labelForCategory(category);
  String get statusLabel => _statusLabel(status);

  /// Distância legível: "80 m" ou "1,2 km".
  String get distanceLabel => distanceM < 1000
      ? '$distanceM m'
      : '${(distanceM / 1000).toStringAsFixed(1).replaceAll('.', ',')} km';

  /// Modelo usado pela tela de detalhe, que busca o restante na API (requer login).
  Report toReport() => Report(
        id: id,
        apiId: id,
        title: categoryLabel,
        description: '',
        location: '$distanceLabel de você',
        details: '',
        category: categoryLabel,
        subcategory: '',
        status: statusLabel,
        organ: '',
        confirmationCount: confirmationCount,
        clientCreatedAt: receivedAt?.toLocal().toString() ?? '',
        forecast: '',
        timeline: const [],
        comments: const [],
      );
}

class NearbyPage {
  const NearbyPage({required this.items, this.nextCursor});

  final List<NearbyReport> items;
  final String? nextCursor;
}

class NearbyException implements Exception {
  NearbyException(this.statusCode);

  final int statusCode;

  @override
  String toString() => 'Falha ao consultar ocorrências próximas ($statusCode).';
}

/// Cliente da rota pública: não envia token, para não vincular a consulta ao usuário.
class NearbyClient {
  NearbyClient({String? baseUrl, http.Client? httpClient})
      : _baseUrl = baseUrl,
        _http = httpClient ?? http.Client();

  final String? _baseUrl;
  final http.Client _http;

  Future<NearbyPage> fetch({
    required double latitude,
    required double longitude,
    int radiusM = 1000,
    String? category,
    String? status,
    int limit = 50,
    String? cursor,
  }) async {
    final uri = Uri.parse('${_baseUrl ?? ApiConfig.baseUrl}/v1/reports/nearby')
        .replace(queryParameters: {
      'lat': '$latitude',
      'lon': '$longitude',
      'radius_m': '$radiusM',
      'limit': '$limit',
      if (category != null) 'category': category,
      if (status != null) 'status': status,
      if (cursor != null) 'cursor': cursor,
    });
    final response = await _http.get(uri, headers: {'Accept': 'application/json'});
    if (response.statusCode != 200) {
      throw NearbyException(response.statusCode);
    }
    final body = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    final items = (body['items'] as List? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(NearbyReport.fromJson)
        .toList();
    return NearbyPage(items: items, nextCursor: body['next_cursor']?.toString());
  }
}

class _CacheEntry {
  _CacheEntry(this.items, this.fetchedAt);

  final List<NearbyReport> items;
  final DateTime fetchedAt;
}

/// Estado do mapa e do feed públicos, com cache por célula (~110 m) por 10 minutos.
class NearbyStore extends ChangeNotifier {
  NearbyStore({NearbyClient? client, DateTime Function()? clock})
      : _client = client ?? NearbyClient(),
        _clock = clock ?? DateTime.now;

  /// Instâncias padrão de cada aba. São separadas porque mapa e feed usam
  /// raio e filtro próprios; uma instância comum faria uma aba sobrescrever a outra.
  static final NearbyStore forMap = NearbyStore();
  static final NearbyStore forFeed = NearbyStore();

  static const cacheTtl = Duration(minutes: 10);

  final NearbyClient _client;
  final DateTime Function() _clock;
  final Map<String, _CacheEntry> _cache = {};

  List<NearbyReport> _items = const [];
  bool _isLoading = false;
  Object? _error;

  List<NearbyReport> get items => _items;
  bool get isLoading => _isLoading;
  Object? get error => _error;

  Future<void> load({
    required double latitude,
    required double longitude,
    int radiusM = 1000,
    String? category,
  }) async {
    final key = [
      latitude.toStringAsFixed(3),
      longitude.toStringAsFixed(3),
      radiusM,
      category ?? '*',
    ].join('|');
    final cached = _cache[key];
    if (cached != null && _clock().difference(cached.fetchedAt) < cacheTtl) {
      _items = cached.items;
      _error = null;
      notifyListeners();
      return;
    }

    _isLoading = true;
    notifyListeners();
    try {
      final page = await _client.fetch(
        latitude: latitude,
        longitude: longitude,
        radiusM: radiusM,
        category: category,
      );
      final sorted = [...page.items]
        ..sort((a, b) => a.distanceM.compareTo(b.distanceM));
      _items = List.unmodifiable(sorted);
      _cache[key] = _CacheEntry(_items, _clock());
      _error = null;
    } catch (error) {
      _error = error;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
