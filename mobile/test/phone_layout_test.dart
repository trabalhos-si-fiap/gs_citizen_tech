// Telas no tamanho do aparelho da demonstração (360 x 800 dp, fontes reais).
// Um "RenderFlex overflowed" durante o layout reprova o teste.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/screens/emergency_screen.dart';
import 'package:reclame_ja_mobile/screens/new_report_wizard.dart';
import 'package:reclame_ja_mobile/screens/post_send_confirmation_screen.dart';
import 'package:reclame_ja_mobile/screens/report_detail_screen.dart';
import 'package:reclame_ja_mobile/screens/tabs/feed_tab.dart';
import 'package:reclame_ja_mobile/screens/tabs/map_tab.dart';
import 'package:reclame_ja_mobile/screens/tabs/profile_tab.dart';
import 'package:reclame_ja_mobile/screens/tabs/reports_tab.dart';
import 'package:reclame_ja_mobile/screens/welcome_screen.dart';
import 'package:reclame_ja_mobile/services/nearby_service.dart';
import 'package:reclame_ja_mobile/services/report_store.dart';

import 'support/nearby_fixtures.dart';
import 'support/phone.dart';

/// Reporte aberto a partir do feed: o "protocolo" exibido é o UUID.
Report _reportFromFeed() => Report(
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

/// Reporte do próprio cidadão já encaminhado, com textos longos de verdade.
Report _ownReport() => Report(
      id: 'RPT-2026-938849',
      title: 'Vazamento de esgoto na frente da escola municipal',
      description:
          'Vazamento de esgoto na frente da escola, cheiro muito forte e sujeira escorrendo pela rua desde ontem.',
      location: 'Em frente ao portão da escola municipal',
      details: '-23.55000, -46.63000',
      category: 'Risco Urbano',
      subcategory: 'Esgoto e vazamento',
      status: 'Em andamento',
      organ: 'Prefeitura Demo — Zeladoria Urbana e Saneamento',
      confirmationCount: 12,
      clientCreatedAt: '19/11/2026 18:30',
      forecast: 'Prazo: 24/11/2026 às 18:00',
      timeline: [
        ReportEvent(
            title: 'Recebido',
            time: '19/11 às 18:30',
            desc: 'Classificado pela IA como Risco Urbano • Esgoto e vazamento.',
            actor: 'Sistema'),
        ReportEvent(
            title: 'Redirecionado',
            time: '19/11 às 18:42',
            desc:
                'Redirecionado para Saneamento Demo: vazamento na rede coletora é competência da concessionária.',
            actor: 'Prefeitura Demo — Zeladoria Urbana'),
        ReportEvent(
            title: 'Em andamento',
            time: '19/11 às 18:50',
            desc: 'Equipe de manutenção a caminho para vistoria.',
            actor: 'Saneamento Demo — Equipe Operacional'),
      ],
      comments: const [
        {
          'author': 'Saneamento Demo',
          'time': 'Hoje às 18:55',
          'text':
              'Equipe enviada; a rede será desobstruída e o trecho lavado ainda hoje.',
          'isOfficial': 'true',
        },
      ],
    );

Future<void> _continue(WidgetTester tester) async {
  await tester.tap(find.text('Continuar'));
  await tester.pump();
}

NearbyStore get _nearby => nearbyStoreWith(const [
      ('a1', 'risco_urbano', 367),
      ('b2', 'saude_atendimento', 496),
      ('c3', 'transporte_publico', 624),
    ]);

void main() {
  setUpAll(loadPhoneFonts);

  testWidgets('map tab filter chips fit on the phone', (tester) async {
    await pumpOnPhone(
      tester,
      MapTab(
        isVisitor: false,
        userName: 'Ana',
        nearbyStore: _nearby,
        locationService: const FixedLocation(),
        showTiles: false,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Risco Urbano'), findsWidgets);
  });

  testWidgets('feed tab filter chips fit on the phone', (tester) async {
    await pumpOnPhone(
      tester,
      FeedTab(
        isVisitor: false,
        userName: 'Ana',
        nearbyStore: _nearby,
        locationService: const FixedLocation(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Transporte'), findsWidgets);
  });

  testWidgets('report detail fits a long protocol and the footer links',
      (tester) async {
    await pumpOnPhone(tester, ReportDetailScreen(report: _reportFromFeed()));
    expect(find.text('Relatar inconsistência'), findsOneWidget);
    await unmount(tester);
  });

  testWidgets('emergency channels fit the card titles and numbers',
      (tester) async {
    await pumpOnPhone(tester, const EmergencyScreen());
    for (final title in [
      'POLÍCIA MILITAR',
      'SAMU - SUPORTE DE SAÚDE',
      'CORPO DE BOMBEIROS',
    ]) {
      expectNotTruncated(tester, title);
    }
    for (final number in ['190', '192', '193']) {
      expectFullyVisible(tester, number);
    }
  });

  testWidgets('new report wizard fits every step on the phone',
      (tester) async {
    void expectEmergencyButtonsVisible() {
      for (final label in ['Polícia 190', 'SAMU 192', 'Bombeiros 193']) {
        expectFullyVisible(tester, label);
      }
    }

    await pumpOnPhone(tester, const NewReportWizard());
    expect(find.text('Passo 1 de 4'), findsOneWidget);
    expectEmergencyButtonsVisible();
    for (final step in [2, 3, 4]) {
      if (step == 4) {
        // Sem foto, o passo 3 só segue com uma descrição (regra da API).
        await tester.enterText(find.byType(TextField), 'Buraco na calçada');
      }
      await _continue(tester);
      expect(find.text('Passo $step de 4'), findsOneWidget);
      if (step < 4) expectEmergencyButtonsVisible();
    }
    await tester.pumpAndSettle();
    expectNotTruncated(tester,
        'Depois do envio, a IA classifica o reporte a partir do seu relato. Você confere e confirma a categoria na próxima tela.');
    expectFullyVisible(tester, 'Deixar a IA classificar');
  });

  group('screens the device sweep could not reach', () {
    testWidgets('welcome screen and e-mail login sheet fit', (tester) async {
      await pumpOnPhone(tester, const WelcomeScreen());
      for (final checkbox in tester.widgetList<Checkbox>(find.byType(Checkbox))) {
        checkbox.onChanged!(true);
      }
      await tester.pump();
      await tester.tap(find.text('Entrar com e-mail').last);
      await tester.pumpAndSettle();
      expect(find.text('Enviar código'), findsOneWidget);
    });

    testWidgets('own report detail fits timeline, organ and comments',
        (tester) async {
      await pumpOnPhone(tester, ReportDetailScreen(report: _ownReport()));
      expectNotTruncated(
          tester, 'Vazamento de esgoto na frente da escola municipal');
      expectNotTruncated(tester, 'Responsável:', contains: true);
      await unmount(tester);
    });

    testWidgets('post-send confirmation fits the protocol and organ',
        (tester) async {
      await pumpOnPhone(
          tester, PostSendConfirmationScreen(report: _ownReport()));
      await tester.pump(const Duration(seconds: 2));
      expect(find.textContaining('RPT-2026-938849'), findsWidgets);
      for (final step in [
        '1. Encaminhamento oficial',
        '2. Vistoria técnica',
        '3. Notificações diretas',
      ]) {
        expectNotTruncated(tester, step);
      }
      await unmount(tester);
    });

    testWidgets('reports tab fits a long own report card', (tester) async {
      ReportStore().addReport(_ownReport());
      await pumpOnPhone(tester, const ReportsTab(isVisitor: false));
      await tester.pump(const Duration(seconds: 1));
      expect(find.textContaining('Vazamento de esgoto'), findsWidgets);
      await unmount(tester);
    });

    testWidgets('profile tab fits a long user name', (tester) async {
      await pumpOnPhone(
        tester,
        const ProfileTab(
            isVisitor: false, userName: 'ana.cidada.moradora.do.centro'),
      );
      expect(find.textContaining('ana.cidada'), findsWidgets);
    });
  });
}
