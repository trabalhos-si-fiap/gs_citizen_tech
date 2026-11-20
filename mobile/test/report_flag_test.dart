// "Relatar inconsistência" no detalhe do reporte envia a sinalização para a
// moderação pela API (`POST /v1/reports/{id}/flag`).

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/screens/report_detail_screen.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';
import 'package:reclame_ja_mobile/services/session_store.dart';

import 'support/phone.dart';

const _apiId = '5e579327-5611-47fe-87eb-b8eea2093c41';

Report _report({String? apiId = _apiId}) => Report(
      id: 'RPT-2026-FLAG01',
      apiId: apiId,
      title: 'Risco Urbano',
      description: '',
      location: '367 m de você',
      details: '',
      category: 'Risco Urbano',
      subcategory: '',
      status: 'Encaminhado',
      organ: '',
      confirmationCount: 0,
      clientCreatedAt: '2026-11-19 15:00:00.000',
      forecast: '',
      timeline: const [],
      comments: const [],
    );

http.Response _json(Object body, int status) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

/// API do detalhe: responde à atualização da tela e entrega a sinalização a
/// [onFlag], guardando as requisições recebidas em [requests].
MockClient _api(
  List<http.Request> requests,
  Future<http.Response> Function(http.Request request) onFlag,
) =>
    MockClient((request) async {
      requests.add(request);
      final path = request.url.path;
      if (path.endsWith('/flag')) return onFlag(request);
      if (path.endsWith('/comments')) return _json({'items': const []}, 200);
      return _json({
        'id': _apiId,
        'protocol': 'RPT-2026-FLAG01',
        'status': 'encaminhado',
        'category': 'risco_urbano',
        'received_at': '2026-11-19T15:00:00Z',
        'lat': -23.55,
        'lon': -46.63,
      }, 200);
    });

/// Abre o detalhe, toca em "Relatar inconsistência" e escolhe [reason].
Future<void> _flagAs(WidgetTester tester, String reason, {String? note}) async {
  await pumpOnPhone(tester, ReportDetailScreen(report: _report()));
  await tester.pump();
  await tester.ensureVisible(find.text('Relatar inconsistência'));
  await tester.tap(find.text('Relatar inconsistência'));
  await tester.pumpAndSettle();
  await tester.tap(find.text(reason));
  await tester.pump();
  if (note != null) {
    await tester.enterText(
        find.descendant(
            of: find.byType(AlertDialog), matching: find.byType(TextField)),
        note);
  }
  await tester.tap(find.text('Enviar sinalização'));
  await tester.pumpAndSettle();
}

void main() {
  setUpAll(loadPhoneFonts);
  setUp(() => SessionStore.accessToken = 'citizen-token');

  testWidgets('sends the chosen reason and note to the flag route',
      (tester) async {
    final requests = <http.Request>[];
    final api = _api(requests, (_) async => _json({'status': 'received'}, 202));

    await http.runWithClient(() async {
      await _flagAs(tester, 'Informação falsa',
          note: 'O buraco já foi tapado faz tempo.');
    }, () => api);

    final flag = requests.singleWhere((r) => r.method == 'POST');
    expect(flag.url.path, '/v1/reports/$_apiId/flag');
    expect(flag.headers['Authorization'], 'Bearer citizen-token');
    expect(jsonDecode(flag.body), {
      'reason': 'falso',
      'note': 'O buraco já foi tapado faz tempo.',
    });
    expect(find.text('Sinalização enviada. A moderação vai revisar este reporte.'),
        findsOneWidget);
    await unmount(tester);
  });

  testWidgets('each reason label maps to the API reason code', (tester) async {
    const reasons = {
      'Conteúdo ofensivo': 'ofensivo',
      'Expõe dados pessoais': 'dados_pessoais',
      'Informação falsa': 'falso',
      'Duplicado/abusivo': 'duplicado_abusivo',
      'Outro': 'outro',
    };
    for (final MapEntry(key: label, value: code) in reasons.entries) {
      final requests = <http.Request>[];
      final api =
          _api(requests, (_) async => _json({'status': 'received'}, 202));

      await http.runWithClient(() => _flagAs(tester, label), () => api);

      final flag = requests.singleWhere((r) => r.method == 'POST');
      expect(jsonDecode(flag.body), {'reason': code}, reason: label);
      await unmount(tester);
    }
  });

  testWidgets('a second flag by the same user says it was already flagged',
      (tester) async {
    final api = _api(
      [],
      (_) async => _json({
        'error': {'code': 'conflict', 'message': 'Você já sinalizou este reporte.'},
      }, 409),
    );

    await http.runWithClient(
        () => _flagAs(tester, 'Conteúdo ofensivo'), () => api);

    expect(
        find.text('Você já sinalizou este reporte. A moderação vai analisá-lo.'),
        findsOneWidget);
    await unmount(tester);
  });

  testWidgets('a visitor is asked to sign in before choosing a reason',
      (tester) async {
    SessionStore.accessToken = null;
    final requests = <http.Request>[];
    final api = _api(requests, (_) async => _json({}, 401));

    await http.runWithClient(() async {
      await pumpOnPhone(tester, ReportDetailScreen(report: _report()));
      await tester.ensureVisible(find.text('Relatar inconsistência'));
      await tester.tap(find.text('Relatar inconsistência'));
      await tester.pump();
    }, () => api);

    expect(find.byType(AlertDialog), findsNothing);
    expect(requests.where((r) => r.method == 'POST'), isEmpty);
    expect(find.text('Entre na sua conta para sinalizar reportes.'),
        findsOneWidget);
    await unmount(tester);
  });

  testWidgets('an expired session (401) is asked to sign in', (tester) async {
    final api = _api(
      [],
      (_) async => _json({
        'error': {'code': 'unauthorized', 'message': 'Não autenticado.'},
      }, 401),
    );

    await http.runWithClient(() => _flagAs(tester, 'Outro'), () => api);

    expect(find.text('Entre na sua conta para sinalizar reportes.'),
        findsOneWidget);
    await unmount(tester);
  });

  testWidgets('a connection failure shows a friendly error', (tester) async {
    final api = _api(
        [], (_) async => throw http.ClientException('Connection refused'));

    await http.runWithClient(() => _flagAs(tester, 'Outro'), () => api);

    expect(
        find.text(
            'Não foi possível enviar a sinalização agora. Tente novamente.'),
        findsOneWidget);
    await unmount(tester);
  });

  testWidgets('a report not sent yet cannot be flagged', (tester) async {
    await pumpOnPhone(tester, ReportDetailScreen(report: _report(apiId: null)));
    await tester.ensureVisible(find.text('Relatar inconsistência'));
    await tester.tap(find.text('Relatar inconsistência'));
    await tester.pump();

    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('A sinalização estará disponível após o envio.'),
        findsOneWidget);
    await unmount(tester);
  });
}
