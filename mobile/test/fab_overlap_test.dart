// O botão flutuante "Reportar problema" do HomeShell fica por cima das abas.
// No fim da rolagem de Perfil, Região e Reportes, o último conteúdo precisa
// sair de baixo dele.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/screens/home_shell.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';

import 'support/phone.dart';

/// Indicadores públicos com órgãos suficientes para a aba Região rolar.
final _api = MockClient((request) async {
  if (!request.url.path.endsWith('/v1/public/metrics')) {
    return http.Response('{}', 404);
  }
  return http.Response(
    jsonEncode({
      'totals': {
        'reports': 120,
        'avg_response_hours': 30.5,
        'resolution_rate': 0.62,
      },
      'by_agency': [
        for (var i = 1; i <= 8; i++)
          {
            'agency': {'id': 'orgao-$i', 'name': 'Órgão Demo $i'},
            'reports': 10 + i,
            'avg_response_hours': 20.0 + i,
            'resolution_rate': 0.5,
          },
      ],
    }),
    200,
    headers: {'content-type': 'application/json; charset=utf-8'},
  );
});

Report _ownReport(int index, {String? title}) => Report(
      id: 'RPT-2026-00000$index',
      title: title ?? 'Buraco na rua $index',
      description: 'Buraco na rua $index',
      location: 'Rua Exemplo, $index',
      details: '',
      category: 'Risco Urbano',
      subcategory: 'Buraco na via',
      status: 'Encaminhado',
      organ: '',
      confirmationCount: 0,
      clientCreatedAt: '19/11/2026 às 20:18',
      forecast: '',
      timeline: const [],
      comments: const [],
    );

/// Abre a aba [tab] do HomeShell e rola o conteúdo até o fim.
Future<void> _scrollTabToEnd(WidgetTester tester, String tab) async {
  await pumpOnPhone(
    tester,
    const HomeShell(isVisitor: false, userName: 'ana.cidada'),
  );
  await tester.tap(find.text(tab));
  await tester.pump(const Duration(milliseconds: 500));
  final visibleScroll = find.byType(Scrollable).hitTestable();
  await tester.drag(visibleScroll.first, const Offset(0, -5000));
  // Espera a rolagem assentar (sem o "repique" além do fim).
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(seconds: 1));
  }
  final position = tester.state<ScrollableState>(visibleScroll.first).position;
  expect(position.pixels, position.maxScrollExtent,
      reason: 'a aba $tab não rolou até o fim');
}

void _expectClearOfFab(WidgetTester tester, List<Finder> lastContent) {
  final fab = tester.getRect(
      find.widgetWithText(FloatingActionButton, 'Reportar problema'));
  for (final finder in lastContent) {
    final rect = tester.getRect(finder);
    // O conteúdo está na tela (a aba rolou até o fim), acima da navegação.
    expect(rect.bottom, lessThanOrEqualTo(fab.bottom + 16),
        reason: '$rect não está visível no fim da rolagem');
    expect(rect.overlaps(fab), isFalse,
        reason: '$rect fica sob o botão flutuante $fab');
  }
}

void main() {
  setUpAll(loadPhoneFonts);

  testWidgets('profile end scrolls clear of the "Reportar problema" button',
      (tester) async {
    await _scrollTabToEnd(tester, 'Perfil');

    _expectClearOfFab(tester, [
      find.widgetWithText(OutlinedButton, 'Sair do Aplicativo'),
      find.text('Voz Cidadã v1.0.0 • Made with IBM Bob'),
    ]);
    await unmount(tester);
  });

  testWidgets('region end scrolls clear of the "Reportar problema" button',
      (tester) async {
    await http.runWithClient(() async {
      await _scrollTabToEnd(tester, 'Região');

      _expectClearOfFab(tester, [
        find.text(
            'Indicadores agregados; grupos com poucos registros não são exibidos.'),
      ]);
      await unmount(tester);
    }, () => _api);
  });

  testWidgets('reports list end scrolls clear of the "Reportar problema" button',
      (tester) async {
    // A lista mostra o mais recente primeiro: o primeiro incluído fica por
    // último.
    final store = ReportStore()..replaceFromApi(const []);
    store.addReport(_ownReport(6, title: 'Último reporte da lista'));
    for (var i = 5; i >= 1; i--) {
      store.addReport(_ownReport(i));
    }

    await _scrollTabToEnd(tester, 'Reportes');

    _expectClearOfFab(tester, [
      find.ancestor(
          of: find.text('Último reporte da lista'), matching: find.byType(Card)),
    ]);
    await unmount(tester);
  });
}
