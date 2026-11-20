// "Meus Reportes": o cartão mostra o relato (ou a categoria) como título, a
// categoria, o endereço e a data local "19/11/2026 às 20:18".

import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/screens/tabs/reports_tab.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';
import 'package:reclame_ja_mobile/services/session_store.dart';

import 'support/phone.dart';

/// Item de `GET /v1/me/reports` no contrato novo.
Map<String, dynamic> _item({
  String id = 'c0ffee00-0000-4000-8000-000000000020',
  String? description = 'Falta de remédio na UBS Central',
  String? category = 'saude_atendimento',
  String? subcategory = 'falta_medicamento',
  String? address = 'Rua Exemplo, 123 – Sé, São Paulo',
  String receivedAt = '2026-11-19T23:18:13Z',
}) =>
    {
      'id': id,
      'protocol': 'RPT-2026-000020',
      'status': 'em_andamento',
      'category': category,
      'subcategory': subcategory,
      'description': description,
      'address': address,
      'lat': -23.55,
      'lon': -46.63,
      'received_at': receivedAt,
      'group_id': id,
      'confirmation_count': 2,
    };

Report _fromList(Map<String, dynamic> item) {
  ReportStore().replaceFromApi([item]);
  return ReportStore().allReports.single;
}

/// "19/11/2026 às 20:18" no fuso do aparelho que roda o teste.
String _local(DateTime utc) {
  final local = utc.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year} às '
      '${two(local.hour)}:${two(local.minute)}';
}

void main() {
  setUpAll(loadPhoneFonts);

  group('list item from the API', () {
    test('uses the description as the title', () {
      expect(_fromList(_item()).title, 'Falta de remédio na UBS Central');
    });

    test('truncates a long description in the title', () {
      final title = _fromList(_item(description: 'Buraco ' * 20)).title;

      expect(title.length, lessThanOrEqualTo(61));
      expect(title, endsWith('…'));
    });

    test('without description the title is the category label', () {
      expect(_fromList(_item(description: null)).title, 'Saúde');
      expect(_fromList(_item(description: '  ')).title, 'Saúde');
    });

    test('carries the readable subcategory sent by the list', () {
      expect(_fromList(_item()).subcategory, 'Falta de medicamento');
    });

    test('shows the address, with the coordinates as the detail', () {
      final report = _fromList(_item());

      expect(report.location, 'Rua Exemplo, 123 – Sé, São Paulo');
      expect(report.details, '-23.55000, -46.63000');
    });

    test('without address the location is the coordinates', () {
      final report = _fromList(_item(address: null));

      expect(report.location, '-23.55000, -46.63000');
      expect(report.details, isEmpty);
    });

    test('formats the received date in local time', () {
      final expected = _local(DateTime.utc(2026, 11, 19, 23, 18, 13));

      expect(_fromList(_item()).clientCreatedAt, expected);
      // Servidores antigos mandam a data sem fuso, mas ela está em UTC.
      expect(
          _fromList(_item(receivedAt: '2026-11-19T23:18:13.065809'))
              .clientCreatedAt,
          expected);
    });
  });

  testWidgets('the card shows title, category, address, date and status',
      (tester) async {
    SessionStore.accessToken = null; // sem rede: mostra o que está no store
    ReportStore().replaceFromApi([_item()]);

    await pumpOnPhone(tester, const ReportsTab(isVisitor: false));

    expect(find.text('Falta de remédio na UBS Central'), findsOneWidget);
    expect(find.text('Saúde • Falta de medicamento'), findsOneWidget);
    expect(find.text('Rua Exemplo, 123 – Sé, São Paulo'), findsOneWidget);
    expect(
        find.text(
            'Criado em ${_local(DateTime.utc(2026, 11, 19, 23, 18, 13))}'),
        findsOneWidget);
    expect(find.text('Em andamento'), findsOneWidget);
    expect(find.text('Ocorrência urbana'), findsNothing);
    await unmount(tester);
  });
}
