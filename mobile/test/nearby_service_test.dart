import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/services/nearby_service.dart';

Map<String, dynamic> _item({
  String id = '8d11c206-f849-4631-9c0f-d27a23fc7634',
  String category = 'risco_urbano',
  String status = 'em_andamento',
  int distance = 120,
}) =>
    {
      'id': id,
      'group_id': '9',
      'status': status,
      'category': category,
      'subcategory': null,
      'lat': -23.5501,
      'lon': -46.6331,
      'confirmation_count': 4,
      'received_at': '2026-11-17T15:00:00Z',
      'distance_m': distance,
    };

http.Response _page(List<Map<String, dynamic>> items, {String? next}) =>
    http.Response(
      jsonEncode({'items': items, 'next_cursor': next}),
      200,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  group('NearbyReport.fromJson', () {
    test('maps API fields and display labels', () {
      final report = NearbyReport.fromJson(_item());

      expect(report.id, '8d11c206-f849-4631-9c0f-d27a23fc7634');
      expect(report.category, 'risco_urbano');
      expect(report.categoryLabel, 'Risco Urbano');
      expect(report.statusLabel, 'Em andamento');
      expect(report.latitude, -23.5501);
      expect(report.longitude, -46.6331);
      expect(report.confirmationCount, 4);
      expect(report.distanceM, 120);
      expect(report.receivedAt, DateTime.utc(2026, 11, 17, 15));
    });

    test('tolerates missing optional fields', () {
      final report = NearbyReport.fromJson({
        'id': 'a',
        'status': 'recebido',
        'category': null,
        'lat': 1,
        'lon': 2,
      });

      expect(report.categoryLabel, 'A classificar');
      expect(report.statusLabel, 'Recebido');
      expect(report.distanceM, 0);
      expect(report.confirmationCount, 0);
    });
  });

  group('NearbyClient', () {
    test('calls public route without authorization and with filters', () async {
      late http.Request captured;
      final client = NearbyClient(
        baseUrl: 'http://api.test',
        httpClient: MockClient((request) async {
          captured = request;
          return _page([_item()], next: 'Mg');
        }),
      );

      final page = await client.fetch(
        latitude: -23.55,
        longitude: -46.63,
        radiusM: 2000,
        category: 'saude_atendimento',
        cursor: 'MQ',
      );

      expect(captured.method, 'GET');
      expect(captured.url.path, '/v1/reports/nearby');
      expect(captured.url.queryParameters, {
        'lat': '-23.55',
        'lon': '-46.63',
        'radius_m': '2000',
        'limit': '50',
        'category': 'saude_atendimento',
        'cursor': 'MQ',
      });
      expect(captured.headers.containsKey('Authorization'), isFalse);
      expect(page.items.single.distanceM, 120);
      expect(page.nextCursor, 'Mg');
    });

    test('throws NearbyException on error status', () async {
      final client = NearbyClient(
        baseUrl: 'http://api.test',
        httpClient: MockClient((_) async => http.Response('{}', 422)),
      );

      expect(
        () => client.fetch(latitude: 0, longitude: 0),
        throwsA(isA<NearbyException>()),
      );
    });
  });

  group('NearbyStore', () {
    late int calls;
    late DateTime now;
    late NearbyStore store;

    setUp(() {
      calls = 0;
      now = DateTime.utc(2026, 11, 18, 12);
      store = NearbyStore(
        client: NearbyClient(
          baseUrl: 'http://api.test',
          httpClient: MockClient((request) async {
            calls++;
            final category = request.url.queryParameters['category'];
            return _page([
              _item(id: 'perto', distance: 50, category: category ?? 'risco_urbano'),
              _item(id: 'longe', distance: 900),
            ]);
          }),
        ),
        clock: () => now,
      );
    });

    test('loads items sorted by distance and notifies listeners', () async {
      var notified = 0;
      store.addListener(() => notified++);

      await store.load(latitude: -23.55, longitude: -46.63);

      expect(store.items.map((r) => r.id), ['perto', 'longe']);
      expect(store.error, isNull);
      expect(store.isLoading, isFalse);
      expect(notified, greaterThanOrEqualTo(2));
    });

    test('reuses cached result for same cell within ten minutes', () async {
      await store.load(latitude: -23.55, longitude: -46.63);
      await store.load(latitude: -23.5502, longitude: -46.6301);
      now = now.add(const Duration(minutes: 9));
      await store.load(latitude: -23.55, longitude: -46.63);

      expect(calls, 1);

      now = now.add(const Duration(minutes: 2));
      await store.load(latitude: -23.55, longitude: -46.63);

      expect(calls, 2);
    });

    test('category filter is part of the cache key', () async {
      await store.load(latitude: -23.55, longitude: -46.63);
      await store.load(
        latitude: -23.55,
        longitude: -46.63,
        category: 'saude_atendimento',
      );

      expect(calls, 2);
      expect(store.items.first.category, 'saude_atendimento');
    });

    test('exposes error when request fails', () async {
      final failing = NearbyStore(
        client: NearbyClient(
          baseUrl: 'http://api.test',
          httpClient: MockClient((_) async => http.Response('', 503)),
        ),
      );

      await failing.load(latitude: 0, longitude: 0);

      expect(failing.items, isEmpty);
      expect(failing.error, isNotNull);
      expect(failing.isLoading, isFalse);
    });
  });

  group('category helpers', () {
    test('map chip labels to API values', () {
      expect(categoryForLabel('Todos'), isNull);
      expect(categoryForLabel('Risco Urbano'), 'risco_urbano');
      expect(categoryForLabel('Transporte'), 'transporte_publico');
      expect(categoryForLabel('Saúde'), 'saude_atendimento');
    });
  });
}
