import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';

void main() {
  test('API identifiers remain separate from displayed protocols', () {
    final store = ReportStore();

    store.replaceFromApi([
      {
        'id': '8d11c206-f849-4631-9c0f-d27a23fc7634',
        'protocol': 'RJ-2026-00123',
        'status': 'em_andamento',
        'category': 'risco_urbano',
        'received_at': '2026-11-17T12:00:00Z',
        'lat': -23.55,
        'lon': -46.63,
      },
    ]);

    final report = store.allReports.single;
    expect(report.id, 'RJ-2026-00123');
    expect(report.apiId, '8d11c206-f849-4631-9c0f-d27a23fc7634');
    expect(report.status, 'Em andamento');
  });

  test('redirected report shows agency, deadline and readable timeline', () {
    final store = ReportStore();

    store.upsertFromApi({
      'id': 'b1d7a7c2-0000-4000-8000-000000000001',
      'protocol': 'RPT-2026-REDIR1',
      'status': 'encaminhado',
      'category': 'risco_urbano',
      'received_at': '2026-11-18T12:00:00Z',
      'lat': -23.55,
      'lon': -46.63,
      'agency': {'id': 'saneamento-demo', 'name': 'Saneamento Demo'},
      'deadline': '2026-11-21T15:30:00',
      'classification': {'category': 'risco_urbano', 'subcategory': 'esgoto_vazamento'},
      'timeline': [
        {'type': 'recebido', 'actor': 'system', 'created_at': '2026-11-18T12:00:00Z'},
        {'type': 'encaminhado', 'actor': 'system', 'created_at': '2026-11-18T12:01:00Z'},
        {
          'type': 'encaminhado',
          'actor': 'agency:prefeitura-demo-zeladoria',
          'justification': 'Vazamento é da rede de esgoto',
          'created_at': '2026-11-18T13:00:00Z',
        },
      ],
    });

    final report = store.allReports.firstWhere((r) => r.id == 'RPT-2026-REDIR1');
    expect(report.organ, 'Saneamento Demo');
    expect(report.subcategory, 'Esgoto vazamento');
    expect(report.forecast, startsWith('Prazo: 21/11/2026'));
    expect(report.timeline.first.title, 'Reporte recebido');
    expect(report.timeline.last.title, 'Redirecionado a outro órgão');
    expect(report.timeline.last.desc, 'Vazamento é da rede de esgoto');
    expect(report.timeline.last.actor, 'Órgão responsável');
  });
}
