// Tela de confirmação depois do envio: mostra a classificação REAL da API
// (consultando o reporte enquanto a IA analisa), a urgência e o órgão
// responsável depois do encaminhamento. Nada de dados inventados.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/screens/post_send_confirmation_screen.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';
import 'package:reclame_ja_mobile/services/session_store.dart';

import 'support/phone.dart';

const _apiId = 'c0ffee00-0000-4000-8000-000000000030';
const _analysing = 'Analisando o seu relato…';

/// Reporte recém-enviado pelo assistente (ainda sem classificação).
Report _sent({bool offline = false}) => Report(
      id: 'RPT-2026-000030',
      apiId: _apiId,
      title: 'Falta de remédio na UBS',
      description: 'Falta de remédio na UBS',
      location: 'Rua Exemplo, 123 – Sé, São Paulo',
      details: '',
      category: 'A classificar',
      subcategory: '',
      status: 'Recebido',
      organ: '',
      confirmationCount: 1,
      clientCreatedAt: '19/11/2026 às 20:18',
      isOffline: offline,
      forecast: '',
      timeline: const [],
      comments: const [],
    );

Map<String, dynamic> _detail(
  String triageState, {
  Map<String, dynamic>? classification,
  String? agency,
}) =>
    {
      'id': _apiId,
      'protocol': 'RPT-2026-000030',
      'status': agency == null ? 'recebido' : 'encaminhado',
      'category': classification?['category'],
      'description': 'Falta de remédio na UBS',
      'address': 'Rua Exemplo, 123 – Sé, São Paulo',
      'lat': -23.55,
      'lon': -46.63,
      'received_at': '2026-11-19T23:18:13Z',
      'triage_state': triageState,
      'classification': classification,
      if (agency != null) 'agency': {'id': 'ubs-demo', 'name': agency},
      'timeline': const [],
    };

const _saude = {
  'category': 'saude_atendimento',
  'subcategory': 'falta_medicamento',
  'urgency': 'alta',
  'confidence': 0.91,
  'immediate_risk': false,
  'model': 'demo',
  'source': 'ai',
};

http.Response _json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

/// API em que o reporte passa de "pendente" a [classified] depois de
/// [pendingReads] consultas; guarda as requisições em [requests].
MockClient _api(
  List<http.Request> requests, {
  int pendingReads = 1,
  Map<String, dynamic>? classified,
}) {
  var reads = 0;
  return MockClient((request) async {
    requests.add(request);
    if (request.url.path.endsWith('/triage')) {
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      final classification = body['action'] == 'correct'
          ? {
              ..._saude,
              'category': body['category'],
              'subcategory': body['subcategory'],
              'source': 'user',
            }
          : _saude;
      return _json(_detail('confirmed',
          classification: classification, agency: 'UBS Demo Sé'));
    }
    reads++;
    if (reads <= pendingReads || classified == null) {
      return _json(_detail('pending_classification'));
    }
    return _json(_detail('awaiting_user', classification: classified));
  });
}

/// `http.runWithClient` pede um cliente a cada requisição; o mesmo
/// [client] guarda o estado entre elas.
http.Client Function() _once(http.Client client) => () => client;

Iterable<http.Request> _reads(List<http.Request> requests) =>
    requests.where((r) => r.method == 'GET');

void main() {
  setUpAll(loadPhoneFonts);
  setUp(() => SessionStore.accessToken = 'citizen-token');

  testWidgets('shows an analysing state while the AI classifies',
      (tester) async {
    await http.runWithClient(() async {
      await pumpOnPhone(tester, PostSendConfirmationScreen(report: _sent()));
      await tester.pump();

      expectNotTruncated(tester, _analysing);
      expect(find.text('Sim, confirmar'), findsNothing);
      await unmount(tester);
    }, () => _api([]));
  });

  testWidgets('shows the real classification and urgency once classified',
      (tester) async {
    final requests = <http.Request>[];
    await http.runWithClient(() async {
      await pumpOnPhone(tester, PostSendConfirmationScreen(report: _sent()));
      await tester.pump();
      expect(find.text(_analysing), findsOneWidget);

      await tester.pump(const Duration(seconds: 3));
      await tester.pump();

      expect(find.text(_analysing), findsNothing);
      expect(find.text('Saúde • Falta de medicamento'), findsOneWidget);
      expect(find.text('Alta'), findsOneWidget);
      expect(find.text('Sim, confirmar'), findsOneWidget);

      // Classificado: para de consultar.
      final readsSoFar = _reads(requests).length;
      await tester.pump(const Duration(seconds: 15));
      expect(_reads(requests).length, readsSoFar);
      await unmount(tester);
    }, _once(_api(requests, classified: _saude)));
  });

  testWidgets('confirming shows the agency the report was routed to',
      (tester) async {
    final requests = <http.Request>[];
    await http.runWithClient(() async {
      await pumpOnPhone(tester, PostSendConfirmationScreen(report: _sent()));
      await tester.pump();
      await tester.pump(const Duration(seconds: 3));
      await tester.pump();
      expect(find.text('Definido após a confirmação da classificação.'),
          findsOneWidget);

      await tester.ensureVisible(find.text('Sim, confirmar'));
      await tester.tap(find.text('Sim, confirmar'));
      await tester.pump();
      await tester.pump();

      expect(find.text('UBS Demo Sé'), findsOneWidget);
      await unmount(tester);
    }, _once(_api(requests, pendingReads: 0, classified: _saude)));

    final triage = requests.singleWhere((r) => r.method == 'POST');
    expect(jsonDecode(triage.body), {'action': 'confirm'});
  });

  testWidgets('correcting lets the citizen pick the right subcategory',
      (tester) async {
    final requests = <http.Request>[];
    await http.runWithClient(() async {
      await pumpOnPhone(tester, PostSendConfirmationScreen(report: _sent()));
      await tester.pump();
      await tester.pump();

      await tester.ensureVisible(find.text('Corrigir dados'));
      await tester.tap(find.text('Corrigir dados'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Falta de médico'), 100,
          scrollable: find.descendant(
              of: find.byType(AlertDialog), matching: find.byType(Scrollable)));
      await tester.ensureVisible(find.text('Falta de médico'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Falta de médico'));
      await tester.pump();
      await tester.tap(find.text('Alterar categoria'));
      await tester.pump();
      await tester.pump();

      expect(find.text('Saúde • Falta de médico'), findsOneWidget);
      await unmount(tester);
    }, _once(_api(requests, pendingReads: 0, classified: _saude)));

    final triage = requests.singleWhere((r) => r.method == 'POST');
    expect(jsonDecode(triage.body), {
      'action': 'correct',
      'category': 'saude_atendimento',
      'subcategory': 'falta_medico',
    });
  });

  testWidgets('shows no made-up neighbours, impact or deadlines',
      (tester) async {
    await http.runWithClient(() async {
      await pumpOnPhone(tester, PostSendConfirmationScreen(report: _sent()));
      await tester.pump();

      for (final fake in [
        'moradores reforçaram',
        'Impacto identificado',
        '48h úteis',
        'Vizinhos engajados',
      ]) {
        expect(find.textContaining(fake), findsNothing, reason: fake);
      }
      expect(find.text('2h'), findsNothing);
      await unmount(tester);
    }, () => _api([]));
  });

  testWidgets('a report waiting for connection is not polled',
      (tester) async {
    final requests = <http.Request>[];
    await http.runWithClient(() async {
      await pumpOnPhone(
          tester, PostSendConfirmationScreen(report: _sent(offline: true)));
      await tester.pump(const Duration(seconds: 10));

      expect(find.text('A classificação acontece depois do envio.'),
          findsOneWidget);
      await unmount(tester);
    }, () => _api(requests));

    expect(requests, isEmpty);
  });
}
