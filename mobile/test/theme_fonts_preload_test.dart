// As fontes do tema precisam estar carregadas antes do primeiro frame. Se o
// app desenha antes, widgets que medem o texto uma única vez (como os chips de
// filtro) guardam a largura da fonte provisória do sistema e cortam o rótulo
// quando a fonte real chega. Arquivo próprio: começa sem fontes no isolate.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/app_theme.dart';
import 'package:reclame_ja_mobile/main.dart';

import 'support/phone.dart';

double _width(String text, TextStyle style) => (TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: TextDirection.ltr,
    )..layout())
        .width;

void main() {
  test('theme fonts are loaded before the app draws its first frame',
      () async {
    useFontCacheDir();

    await preloadThemeFonts();

    final chipLabel = AppTheme.lightTheme()
        .textTheme
        .labelLarge!
        .copyWith(fontSize: 12, fontWeight: FontWeight.bold);
    // JetBrains Mono é monoespaçada: 5 letras x 0,6 em x 12 px ≈ 36 px.
    expect(_width('Todos', chipLabel), closeTo(36.1, 0.5));
  });
}
