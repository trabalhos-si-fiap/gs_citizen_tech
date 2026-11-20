// Envio do novo reporte: sem categoria escolhida, a IA classifica sozinha
// (o app não manda palpite); o local vai como endereço legível, com as
// coordenadas só como detalhe.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/screens/new_report_wizard.dart';
import 'package:reclame_ja_mobile/services/address_service.dart';
import 'package:reclame_ja_mobile/services/outbox_store.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';
import 'package:reclame_ja_mobile/services/session_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/phone.dart';

const _address = 'Rua Exemplo, 123 – Sé, São Paulo';
const _coordinates = '-23.55000, -46.63000';
const _reportId = 'c0ffee00-0000-4000-8000-000000000010';

Future<Position> _gps() async => Position(
      latitude: -23.55,
      longitude: -46.63,
      timestamp: DateTime.utc(2026, 11, 19, 23, 18),
      accuracy: 8,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );

class _FakeAddressLookup implements AddressLookup {
  _FakeAddressLookup(this._answer);

  final Future<String?> Function() _answer;

  @override
  Future<String?> addressFor(double latitude, double longitude) => _answer();
}

/// API do envio: cria o reporte e responde à tela de confirmação.
MockClient _api(List<Map<String, dynamic>> created) =>
    MockClient((request) async {
      if (request.method == 'POST' && request.url.path == '/v1/reports') {
        created.add(jsonDecode(request.body) as Map<String, dynamic>);
        return _json({
          'id': _reportId,
          'protocol': 'RPT-2026-000010',
          'status': 'recebido',
          'received_at': '2026-11-19T23:18:13Z',
          'triage_state': 'pending_classification',
        }, 201);
      }
      return _json({
        'id': _reportId,
        'protocol': 'RPT-2026-000010',
        'status': 'recebido',
        'category': null,
        'lat': -23.55,
        'lon': -46.63,
        'address': _address,
        'received_at': '2026-11-19T23:18:13Z',
        'triage_state': 'pending_classification',
        'classification': null,
        'timeline': const [],
        'items': const [],
      }, 200);
    });

http.Response _json(Object body, int status) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

Future<void> _continue(WidgetTester tester) async {
  await tester.tap(find.text('Continuar'));
  await tester.pump();
}

/// Abre o assistente e preenche até o passo 4, com GPS e endereço falsos.
Future<void> _fillUntilStep4(
  WidgetTester tester, {
  Future<String?> Function()? address,
  bool offline = false,
}) async {
  await pumpOnPhone(
    tester,
    NewReportWizard(
      positionSource: _gps,
      addressLookup: _FakeAddressLookup(address ?? () async => _address),
    ),
  );
  if (offline) {
    await tester.tap(find.byType(Switch).first);
    await tester.pump();
  }
  await _continue(tester);
  await tester.tap(find.text('Capturar GPS'));
  await tester.pump();
  await tester.pump();
  await _continue(tester);
  await tester.enterText(find.byType(TextField), 'Falta de remédio na UBS');
  await _continue(tester);
  expect(find.text('Passo 4 de 4'), findsOneWidget);
}

Future<void> _send(WidgetTester tester) async {
  await tester.tap(find.text('Enviar solicitação'));
  await tester.pump();
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
}

void main() {
  setUpAll(loadPhoneFonts);
  setUp(() {
    SessionStore.accessToken = 'citizen-token';
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('step 4 starts with the AI deciding and no fake AI guess',
      (tester) async {
    await _fillUntilStep4(tester);

    expect(find.text('Deixar a IA classificar'), findsOneWidget);
    expect(
        find.descendant(
            of: find.ancestor(
                of: find.text('Deixar a IA classificar'),
                matching: find.byType(InkWell)),
            matching: find.byIcon(Icons.check)),
        findsOneWidget);
    expect(find.text('98% certeza'), findsNothing);
    expect(find.textContaining('Identificamos o tema'), findsNothing);
    expectNotTruncated(tester,
        'Depois do envio, a IA classifica o reporte a partir do seu relato. Você confere e confirma a categoria na próxima tela.');
  });

  testWidgets('by default no category is sent, so the AI decides',
      (tester) async {
    final created = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      await _fillUntilStep4(tester);
      await _send(tester);
      await unmount(tester);
    }, () => _api(created));

    expect(created.single, isNot(contains('category')));
  });

  testWidgets('picking "Atendimento UBS" sends saude_atendimento',
      (tester) async {
    final created = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      await _fillUntilStep4(tester);
      await tester.tap(find.text('Atendimento UBS'));
      await tester.pump();
      await _send(tester);
      await unmount(tester);
    }, () => _api(created));

    expect(created.single['category'], 'saude_atendimento');
  });

  testWidgets('the captured address is shown in step 2, sent and confirmed',
      (tester) async {
    final created = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      await pumpOnPhone(
        tester,
        NewReportWizard(
          positionSource: _gps,
          addressLookup: _FakeAddressLookup(() async => _address),
        ),
      );
      await _continue(tester);
      await tester.tap(find.text('Capturar GPS'));
      await tester.pump();
      await tester.pump();

      expectNotTruncated(tester, _address);
      expect(find.textContaining(_coordinates), findsOneWidget); // secundário

      await _continue(tester);
      await tester.enterText(find.byType(TextField), 'Falta de remédio na UBS');
      await _continue(tester);
      await _send(tester);

      expect(find.text('Confirmação'), findsOneWidget);
      expect(find.text(_address), findsOneWidget);
      await unmount(tester);
    }, () => _api(created));

    expect(created.single['address'], _address);
  });

  testWidgets('without an address the coordinates are shown and sending works',
      (tester) async {
    final created = <Map<String, dynamic>>[];
    await http.runWithClient(() async {
      await _fillUntilStep4(tester,
          address: () async => throw Exception('sem geocodificador'));
      await _send(tester);
      await unmount(tester);
    }, () => _api(created));

    expect(created.single, isNot(contains('address')));
  });

  testWidgets('a geocoder that never answers falls back to the coordinates',
      (tester) async {
    await pumpOnPhone(
      tester,
      NewReportWizard(
        positionSource: _gps,
        addressLookup: _FakeAddressLookup(() => Completer<String?>().future),
      ),
    );
    await _continue(tester);
    await tester.tap(find.text('Capturar GPS'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 6));

    expect(find.text(_coordinates), findsOneWidget);
    expect(find.text('Localizando'), findsNothing);
  });

  testWidgets('the new report is dated now, not with a fixed demo date',
      (tester) async {
    // Offline: o reporte local fica no store sem ser trocado pelo da API.
    await _fillUntilStep4(tester, offline: true);
    await _send(tester);
    await unmount(tester);

    final report = ReportStore().allReports.first;
    final today = formatDateTime(DateTime.now()).split(' às ').first;
    expect(report.clientCreatedAt, startsWith('$today às '));
    expect(report.timeline.first.time, startsWith('$today às '));
  });

  testWidgets('the app does not guess the agency or the deadline',
      (tester) async {
    // Offline a confirmação mostra o reporte local, sem dados da API.
    await _fillUntilStep4(tester, offline: true);
    await tester.tap(find.text('Atendimento UBS'));
    await tester.pump();
    await _send(tester);

    expect(find.text('Definido após a confirmação da classificação.'),
        findsOneWidget);
    expect(find.textContaining('Ouvidoria de Saúde'), findsNothing);
    final report = ReportStore().allReports.first;
    expect(report.organ, isEmpty);
    expect(report.forecast, isEmpty);
    await unmount(tester);
  });

  testWidgets('offline, the pending report keeps the address and no category',
      (tester) async {
    await _fillUntilStep4(tester, offline: true);
    await _send(tester);

    final pending = await OutboxStore.load();
    expect(pending.single['address'], _address);
    expect(pending.single, isNot(contains('category')));
    await unmount(tester);
  });
}
