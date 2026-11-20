// No aparelho, o google_fonts lê as fontes do disco depois do primeiro frame:
// o texto sai antes na fonte do sistema, mais estreita que a JetBrains Mono, e
// precisa ser remedido quando a fonte chega. Cada cenário fica num arquivo
// próprio porque as fontes carregadas valem para o isolate inteiro.

import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/screens/tabs/map_tab.dart';

import 'support/nearby_fixtures.dart';
import 'support/phone.dart';

void main() {
  setUpAll(loadNarrowFallbackFonts);

  testWidgets('map filter chips still fit after the Google Fonts load',
      (tester) async {
    await pumpOnPhone(
      tester,
      MapTab(
        isVisitor: false,
        userName: 'Ana',
        nearbyStore: nearbyStoreWith(const []),
        locationService: const FixedLocation(),
        showTiles: false,
      ),
    );
    await fontsArriveAfterFirstFrame(tester);
    expect(find.text('Transporte'), findsOneWidget);
  });
}
