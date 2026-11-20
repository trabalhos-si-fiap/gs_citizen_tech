import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/services/location_service.dart';
import 'package:reclame_ja_mobile/services/nearby_service.dart';

import 'phone.dart';

/// Localização fixa (a mesma dos demais testes do mapa e do feed).
class FixedLocation implements LocationService {
  const FixedLocation();

  @override
  Future<GeoPoint> current() async => const GeoPoint(-23.55, -46.63);
}

/// Store do mapa/feed respondendo com [reports] (id, categoria, distância).
NearbyStore nearbyStoreWith(
  List<(String, String, int)> reports,
) =>
    NearbyStore(
      client: NearbyClient(
        baseUrl: 'http://api.test',
        httpClient: MockClient((request) async => http.Response(
              jsonEncode({
                'items': [
                  for (final (id, category, distance) in reports)
                    {
                      'id': id,
                      'group_id': id,
                      'status': 'encaminhado',
                      'category': category,
                      'lat': -23.55 + distance / 111000,
                      'lon': -46.63,
                      'confirmation_count': 0,
                      'received_at': '2026-11-19T15:00:00Z',
                      'distance_m': distance,
                    },
                ],
                'next_cursor': null,
              }),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            )),
      ),
    );

/// Simula a leitura das fontes do disco terminando depois do primeiro frame.
Future<void> fontsArriveAfterFirstFrame(WidgetTester tester) async {
  await tester.runAsync(loadPhoneFonts);
  await tester.pumpAndSettle();
}
