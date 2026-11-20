import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/app_theme.dart';

/// Galaxy S20 FE (SM-G781B), aparelho usado na demonstração:
/// 1080 x 2400 px com densidade 3.0, ou seja, 360 x 800 dp.
const phonePhysicalSize = Size(1080, 2400);
const phoneDevicePixelRatio = 3.0;

/// Barra de status (24 dp) e barra de navegação com 3 botões (48 dp), em px.
const _phonePadding = FakeViewPadding(top: 72, bottom: 144);

final _fontsDir = Directory('test/fonts').absolute.path;

/// Carrega as mesmas fontes que o app baixou no aparelho (Google Fonts).
///
/// O google_fonts procura `<família>_<hash>.ttf` na pasta de suporte do app
/// antes de ir à rede; apontar essa pasta para `test/fonts` evita downloads e
/// faz o teste medir o texto com as métricas reais. Sem isso o Flutter usa a
/// fonte de teste (glifos quadrados) e os overflows do aparelho não aparecem.
Future<void> loadPhoneFonts() async {
  useFontCacheDir();
  final files = Directory(_fontsDir)
      .listSync()
      .whereType<File>()
      .where((file) => file.path.endsWith('.ttf'));
  for (final file in files) {
    final name = file.uri.pathSegments.last;
    final family = name.substring(0, name.lastIndexOf('_'));
    final bytes = await file.readAsBytes();
    await (FontLoader(family)..addFont(Future.value(bytes.buffer.asByteData())))
        .load();
  }
}

/// Aponta a pasta de suporte do app para `test/fonts`, onde o google_fonts
/// encontra as fontes em vez de baixá-las (a leitura fica pendente até o
/// teste liberar o event loop, como a leitura do disco no aparelho).
void useFontCacheDir() {
  TestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
    const MethodChannel('plugins.flutter.io/path_provider'),
    (call) async => _fontsDir,
  );
}

/// Simula o primeiro frame do aparelho, quando as fontes do Google Fonts ainda
/// não foram lidas do disco e o texto sai na fonte padrão do sistema, mais
/// estreita que a JetBrains Mono. Registra uma fonte estreita (Hanken
/// Grotesk regular, peso 400) sob os nomes de família do google_fonts; quando
/// [loadPhoneFonts] registra as fontes reais, elas vencem a escolha por peso.
Future<void> loadNarrowFallbackFonts() async {
  useFontCacheDir();
  final files = Directory(_fontsDir).listSync().whereType<File>();
  final narrow = files.firstWhere(
    (file) => file.uri.pathSegments.last.startsWith('HankenGrotesk_regular_'),
  );
  final bytes = (await narrow.readAsBytes()).buffer.asByteData();
  for (final file in files.where((file) => file.path.endsWith('.ttf'))) {
    final name = file.uri.pathSegments.last;
    final family = name.substring(0, name.lastIndexOf('_'));
    if (family == 'HankenGrotesk_regular') continue;
    await (FontLoader(family)..addFont(Future.value(bytes))).load();
  }
}

/// Simula a tela do aparelho no teste e restaura no fim.
void usePhoneScreen(WidgetTester tester) {
  tester.view.physicalSize = phonePhysicalSize;
  tester.view.devicePixelRatio = phoneDevicePixelRatio;
  tester.view.padding = _phonePadding;
  tester.view.viewPadding = _phonePadding;
  addTearDown(tester.view.reset);
}

/// Monta [child] com o tema do app, na tela do aparelho.
Future<void> pumpOnPhone(WidgetTester tester, Widget child) async {
  usePhoneScreen(tester);
  await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme(), home: child));
  await tester.pump();
}

/// Garante que [text] aparece inteiro numa linha: largura renderizada igual
/// à natural (medida agora, com as fontes atuais) e sem quebra.
void expectFullyVisible(WidgetTester tester, String text) {
  expect(find.text(text), findsWidgets);
  for (final paragraph
      in tester.renderObjectList<RenderParagraph>(find.text(text))) {
    final natural = TextPainter(
      text: paragraph.text,
      textDirection: TextDirection.ltr,
      textScaler: paragraph.textScaler,
      maxLines: 1,
    )..layout();
    expect(paragraph.size.width, greaterThanOrEqualTo(natural.width - 0.5),
        reason: '"$text" foi cortado (${paragraph.size.width} < ${natural.width})');
    expect(paragraph.size.height, lessThanOrEqualTo(natural.height + 0.5),
        reason: '"$text" quebrou em mais de uma linha');
  }
}

/// Garante que [text] não foi cortado nem trocado por reticências (pode
/// quebrar em mais de uma linha).
void expectNotTruncated(WidgetTester tester, String text,
    {bool contains = false}) {
  final finder = contains ? find.textContaining(text) : find.text(text);
  expect(finder, findsWidgets);
  for (final paragraph in tester.renderObjectList<RenderParagraph>(finder)) {
    expect(paragraph.didExceedMaxLines, isFalse,
        reason: '"$text" foi cortado com reticências');
    final natural = TextPainter(
      text: paragraph.text,
      textDirection: TextDirection.ltr,
      textScaler: paragraph.textScaler,
    )..layout(maxWidth: paragraph.size.width);
    expect(paragraph.size.height, greaterThanOrEqualTo(natural.height - 0.5),
        reason: '"$text" foi cortado na altura');
  }
}

/// Desmonta a árvore para cancelar timers periódicos das telas.
Future<void> unmount(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
}
