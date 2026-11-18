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
}
