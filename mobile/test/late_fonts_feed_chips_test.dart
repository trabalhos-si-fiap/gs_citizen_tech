// Mesmo cenário de `late_fonts_map_chips_test.dart`, para o feed (arquivo
// separado: as fontes carregadas valem para o isolate inteiro).

import 'package:flutter_test/flutter_test.dart';
import 'package:reclame_ja_mobile/screens/tabs/feed_tab.dart';

import 'support/nearby_fixtures.dart';
import 'support/phone.dart';

void main() {
  setUpAll(loadNarrowFallbackFonts);

  testWidgets('feed filter chips still fit after the Google Fonts load',
      (tester) async {
    await pumpOnPhone(
      tester,
      FeedTab(
        isVisitor: false,
        userName: 'Ana',
        nearbyStore: nearbyStoreWith(const []),
        locationService: const FixedLocation(),
      ),
    );
    await fontsArriveAfterFirstFrame(tester);
    expect(find.text('Transporte'), findsOneWidget);
  });
}
