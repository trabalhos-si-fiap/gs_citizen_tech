// O assistente de novo reporte começa com os campos vazios (o exemplo fica só
// no hint) e não segue sem descrição nem foto, que é a regra da API.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/screens/new_report_wizard.dart';

import 'support/phone.dart';

const _referenceHint = 'Ex: Próximo à praça ou poste nº 12';
const _descriptionHint =
    'Ex: Grande buraco aberto na pista da direita após a chuva forte, oferecendo risco de queda...';
const _missingDescription = 'Descreva o que você observou ou anexe uma foto.';

Finder _fieldWithHint(String hint) => find.byWidgetPredicate(
    (widget) => widget is TextField && widget.decoration?.hintText == hint);

String _textOf(WidgetTester tester, String hint) =>
    tester.widget<TextField>(_fieldWithHint(hint)).controller!.text;

Future<void> _continue(WidgetTester tester) async {
  await tester.tap(find.text('Continuar'));
  await tester.pump();
}

/// Abre o assistente (sem foto) e avança até [step].
Future<void> _openAtStep(WidgetTester tester, int step) async {
  await pumpOnPhone(tester, const NewReportWizard());
  for (var current = 1; current < step; current++) {
    await _continue(tester);
  }
  expect(find.text('Passo $step de 4'), findsOneWidget);
}

void main() {
  setUpAll(loadPhoneFonts);

  testWidgets('reference point starts empty, with the example only as hint',
      (tester) async {
    await _openAtStep(tester, 2);

    expect(_textOf(tester, _referenceHint), isEmpty);
  });

  testWidgets('description starts empty, with the example only as hint',
      (tester) async {
    await _openAtStep(tester, 3);

    expect(_textOf(tester, _descriptionHint), isEmpty);
  });

  testWidgets('continuing without description or photo asks for a description',
      (tester) async {
    await _openAtStep(tester, 3);

    await _continue(tester);

    expect(find.text('Passo 3 de 4'), findsOneWidget);
    expectNotTruncated(tester, _missingDescription);
  });

  testWidgets('a typed description lets the user continue', (tester) async {
    await _openAtStep(tester, 3);
    await _continue(tester);

    await tester.enterText(
        _fieldWithHint(_descriptionHint), 'Buraco grande na calçada');
    await tester.pump();
    expect(find.text(_missingDescription), findsNothing);
    await _continue(tester);

    expect(find.text('Passo 4 de 4'), findsOneWidget);
  });

  testWidgets('step 3 has no simulated voice dictation button',
      (tester) async {
    await _openAtStep(tester, 3);

    // O teclado do aparelho já tem a tecla de ditado; o botão só colava um
    // texto pronto.
    expect(find.byTooltip('Ditar por voz'), findsNothing);
    expect(find.byIcon(Icons.mic), findsNothing);
  });

  testWidgets('continuing without a photo never claims one was attached',
      (tester) async {
    await pumpOnPhone(tester, const NewReportWizard());

    await _continue(tester);
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Foto anexada com sucesso!'), findsNothing);
    expect(
        find.text(
            'Sem foto: anexar uma imagem ajuda a equipe a avaliar o problema.'),
        findsOneWidget);
  });

  testWidgets('description stops at 300 characters', (tester) async {
    await _openAtStep(tester, 3);

    await tester.enterText(_fieldWithHint(_descriptionHint), 'a' * 350);
    await tester.pump();

    expect(_textOf(tester, _descriptionHint), hasLength(300));
    expect(find.text('300 / 300'), findsOneWidget);
  });

  testWidgets('description indicator and counter follow what was typed',
      (tester) async {
    await _openAtStep(tester, 3);
    expect(find.text('Boa descrição informada'), findsNothing);
    expect(find.text('0 / 300'), findsOneWidget);

    await tester.enterText(
        _fieldWithHint(_descriptionHint), 'Buraco grande na calçada');
    await tester.pump();

    expect(find.text('Boa descrição informada'), findsOneWidget);
    expect(find.text('24 / 300'), findsOneWidget);
  });

  test('a report needs a photo or a description, as the API requires', () {
    expect(reportHasContent(hasPhoto: true, description: ''), isTrue);
    expect(reportHasContent(hasPhoto: false, description: 'Buraco'), isTrue);
    expect(reportHasContent(hasPhoto: false, description: '   '), isFalse);
  });
}
