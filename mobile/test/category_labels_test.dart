// A API devolve categoria e subcategoria como códigos (risco_urbano,
// esgoto_vazamento); o app mostra rótulos legíveis.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/screens/report_detail_screen.dart';
import 'package:reclame_ja_mobile/services/category_labels.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';

import 'support/phone.dart';

const _apiId = 'c0ffee00-0000-4000-8000-000000000004';

/// Reporte como `GET /v1/reports/{id}` devolve.
Map<String, dynamic> _apiReport() => {
      'id': _apiId,
      'protocol': 'RPT-2026-LABEL4',
      'status': 'encaminhado',
      'category': 'risco_urbano',
      'received_at': '2026-11-19T15:00:00Z',
      'lat': -23.55,
      'lon': -46.63,
      'classification': {
        'category': 'risco_urbano',
        'subcategory': 'esgoto_vazamento',
      },
      'timeline': const [],
    };

void main() {
  group('labelForCategory', () {
    test('maps API categories to the labels used in the app', () {
      expect(labelForCategory('risco_urbano'), 'Risco Urbano');
      expect(labelForCategory('transporte_publico'), 'Transporte');
      expect(labelForCategory('saude_atendimento'), 'Saúde');
      expect(labelForCategory('a_classificar'), 'A classificar');
    });

    test('missing category reads "A classificar"', () {
      expect(labelForCategory(null), 'A classificar');
      expect(labelForCategory(''), 'A classificar');
    });

    test('unknown category is still readable', () {
      expect(labelForCategory('meio_ambiente'), 'Meio ambiente');
    });
  });

  group('labelForSubcategory', () {
    test('maps taxonomy subcategories to readable labels', () {
      expect(labelForSubcategory('esgoto_vazamento'), 'Esgoto e vazamento');
      expect(labelForSubcategory('buraco_via'), 'Buraco na via');
      expect(labelForSubcategory('arvore_risco'), 'Árvore com risco de queda');
      expect(labelForSubcategory('calcada_danificada'), 'Calçada danificada');
      expect(labelForSubcategory('onibus_atraso_lotacao'),
          'Ônibus atrasado ou lotado');
      expect(labelForSubcategory('falta_medicamento'), 'Falta de medicamento');
    });

    test('missing or unclassified subcategory is left empty', () {
      expect(labelForSubcategory(null), '');
      expect(labelForSubcategory(''), '');
      expect(labelForSubcategory('a_classificar'), '');
    });

    test('unknown subcategory is still readable', () {
      expect(labelForSubcategory('poste_caido'), 'Poste caido');
    });
  });

  test('report from the API carries readable category and subcategory', () {
    ReportStore().upsertFromApi(_apiReport());

    final report =
        ReportStore().allReports.firstWhere((r) => r.apiId == _apiId);
    expect(report.category, 'Risco Urbano');
    expect(report.subcategory, 'Esgoto e vazamento');
  });

  group('report detail photo chip', () {
    setUpAll(loadPhoneFonts);

    testWidgets('shows the readable category of an API report',
        (tester) async {
      final api = MockClient((request) async => http.Response(
            jsonEncode(request.url.path.endsWith('/comments')
                ? {'items': const []}
                : _apiReport()),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          ));
      await http.runWithClient(() async {
        ReportStore().upsertFromApi(_apiReport());
        final report =
            ReportStore().allReports.firstWhere((r) => r.apiId == _apiId);

        await pumpOnPhone(tester, ReportDetailScreen(report: report));
        await tester.pump();

        expect(find.text('Risco Urbano • Esgoto e vazamento'), findsOneWidget);
        expect(find.textContaining('risco_urbano'), findsNothing);
        await unmount(tester);
      }, () => api);
    });

    testWidgets('omits the separator when there is no subcategory',
        (tester) async {
      final report = Report(
        id: '5e579327-5611-47fe-87eb-b8eea2093c41',
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

      await pumpOnPhone(tester, ReportDetailScreen(report: report));

      expect(find.textContaining('Risco Urbano •'), findsNothing);
      await unmount(tester);
    });
  });
}
