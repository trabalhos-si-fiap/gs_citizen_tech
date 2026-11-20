import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/screens/tabs/feed_tab.dart';
import 'package:reclame_ja_mobile/screens/tabs/map_tab.dart';
import 'package:reclame_ja_mobile/services/location_service.dart';
import 'package:reclame_ja_mobile/services/nearby_service.dart';

Map<String, dynamic> _item(String id, String category, int distance) => {
      'id': id,
      'group_id': id,
      'status': 'recebido',
      'category': category,
      'lat': -23.55 + distance / 111000,
      'lon': -46.63,
      'confirmation_count': 2,
      'received_at': '2026-11-17T15:00:00Z',
      'distance_m': distance,
    };

class _FixedLocation implements LocationService {
  const _FixedLocation([this.point = const GeoPoint(-23.55, -46.63)]);

  final GeoPoint point;

  @override
  Future<GeoPoint> current() async => point;
}

NearbyStore _store(List<Uri> requests) => NearbyStore(
      client: NearbyClient(
        baseUrl: 'http://api.test',
        httpClient: MockClient((request) async {
          requests.add(request.url);
          final category = request.url.queryParameters['category'];
          final items = [
            _item('a1', 'risco_urbano', 80),
            _item('b2', 'saude_atendimento', 640),
          ].where((item) => category == null || item['category'] == category);
          return http.Response(
            jsonEncode({'items': items.toList(), 'next_cursor': null}),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
      ),
    );

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('feed lists public nearby reports from the API', (tester) async {
    final requests = <Uri>[];
    await tester.pumpWidget(_wrap(FeedTab(
      isVisitor: true,
      userName: 'Visitante',
      nearbyStore: _store(requests),
      locationService: const _FixedLocation(),
    )));
    await tester.pumpAndSettle();

    expect(requests.single.queryParameters['lat'], '-23.55');
    expect(find.text('Risco Urbano'), findsWidgets);
    expect(find.text('80 m'), findsOneWidget);
    expect(find.text('640 m'), findsOneWidget);
    expect(find.textContaining('2 ocorrências'), findsOneWidget);
  });

  testWidgets('feed category chip queries the API with the filter',
      (tester) async {
    final requests = <Uri>[];
    await tester.pumpWidget(_wrap(FeedTab(
      isVisitor: true,
      userName: 'Visitante',
      nearbyStore: _store(requests),
      locationService: const _FixedLocation(),
    )));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilterChip, 'Saúde'));
    await tester.pumpAndSettle();

    expect(requests.last.queryParameters['category'], 'saude_atendimento');
    expect(find.text('640 m'), findsOneWidget);
    expect(find.text('80 m'), findsNothing);
  });

  testWidgets('map camera follows device location on first load',
      (tester) async {
    // Longe do centro padrão: marcadores fora da câmera não são desenhados.
    const far = GeoPoint(-3.7319, -38.5267);
    final store = NearbyStore(
      client: NearbyClient(
        baseUrl: 'http://api.test',
        httpClient: MockClient((request) async => http.Response(
              jsonEncode({
                'items': [
                  {
                    ..._item('c3', 'risco_urbano', 30),
                    'lat': far.latitude,
                    'lon': far.longitude,
                  }
                ],
                'next_cursor': null,
              }),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            )),
      ),
    );
    await tester.pumpWidget(_wrap(MapTab(
      isVisitor: true,
      userName: 'Visitante',
      nearbyStore: store,
      locationService: const _FixedLocation(far),
      showTiles: false,
    )));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('nearby-marker-c3')), findsOneWidget);
  });

  testWidgets('map shows one marker per nearby report', (tester) async {
    final requests = <Uri>[];
    await tester.pumpWidget(_wrap(MapTab(
      isVisitor: true,
      userName: 'Visitante',
      nearbyStore: _store(requests),
      locationService: const _FixedLocation(),
      showTiles: false,
    )));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('nearby-marker-a1')), findsOneWidget);
    expect(find.byKey(const ValueKey('nearby-marker-b2')), findsOneWidget);
  });

  testWidgets('map tiles stay sharp on high-density screens', (tester) async {
    // Densidade 3.0, como o Galaxy S20 FE. Sem retina, o tile de 256 px é
    // esticado 3x e o mapa fica borrado.
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_wrap(MapTab(
      isVisitor: true,
      userName: 'Visitante',
      nearbyStore: _store([]),
      locationService: const _FixedLocation(),
    )));
    await tester.pump();

    final tiles = tester.widget<TileLayer>(find.byType(TileLayer));
    expect(tiles.resolvedRetinaMode, RetinaMode.simulation);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('map marks the citizen position as "you are here"',
      (tester) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(_wrap(MapTab(
      isVisitor: true,
      userName: 'Visitante',
      nearbyStore: _store([]),
      locationService: const _FixedLocation(),
      showTiles: false,
    )));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel(RegExp('Sua localização')), findsOneWidget);
    expect(find.text('Você está aqui'), findsOneWidget);
    semantics.dispose();
  });
}
