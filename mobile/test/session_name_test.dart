// O nome da saudação é guardado com a sessão: ao reabrir o app já logado, o
// munícipe continua vendo "Olá, <nome>" em vez de "Olá, Munícipe".

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reclame_ja_mobile/main.dart';
import 'package:reclame_ja_mobile/services/session_store.dart';

import 'support/phone.dart';

/// Armazenamento seguro simulado; o teste inspeciona o que ficou gravado.
Map<String, String> _storage(Map<String, String> values) {
  final stored = {...values};
  FlutterSecureStorage.setMockInitialValues(stored);
  return stored;
}

const _tokens = {
  'reclame_ja_access_token': 'access-token',
  'reclame_ja_refresh_token': 'refresh-token',
};

/// Abre o app como o `main()` faz depois de restaurar a sessão.
Future<void> _openApp(WidgetTester tester) async {
  usePhoneScreen(tester);
  await tester.pumpWidget(
    ReclameJaApp(isAuthenticated: SessionStore.accessToken != null),
  );
  await tester.pump();
}

void main() {
  setUpAll(loadPhoneFonts);

  testWidgets('reopening the app logged in greets the user by the stored name',
      (tester) async {
    _storage({..._tokens, 'reclame_ja_display_name': 'ana.cidada'});
    await SessionStore.restore();

    await _openApp(tester);

    expect(find.text('Olá, ana.cidada 👋'), findsOneWidget);
    await unmount(tester);
  });

  testWidgets('a session saved before the name existed uses the e-mail user',
      (tester) async {
    _storage({..._tokens, 'reclame_ja_account_email': 'ana.cidada@exemplo.com'});
    await SessionStore.restore();

    await _openApp(tester);

    expect(find.text('Olá, ana.cidada 👋'), findsOneWidget);
    await unmount(tester);
  });

  testWidgets('without a stored name the greeting falls back to "Munícipe"',
      (tester) async {
    _storage(_tokens);
    await SessionStore.restore();

    await _openApp(tester);

    expect(find.text('Olá, Munícipe 👋'), findsOneWidget);
    await unmount(tester);
  });

  test('saving the display name persists it for the next launch', () async {
    final stored = _storage({});

    await SessionStore.saveDisplayName('ana.cidada');

    expect(stored['reclame_ja_display_name'], 'ana.cidada');
  });

  testWidgets('logging in by e-mail stores the name shown in the greeting',
      (tester) async {
    final stored = _storage({});
    await SessionStore.restore(); // começa deslogado
    // Login real da tela de boas-vindas, com a API respondendo pelo MockClient.
    final api = MockClient((request) async {
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      if (!body.containsKey('code')) {
        return http.Response(jsonEncode({'status': 'otp_sent'}), 202);
      }
      return http.Response(
        jsonEncode({
          'access_token': 'access-token',
          'refresh_token': 'refresh-token',
          'expires_in': 900,
          'user': {
            'id': 'u1',
            'email': 'ana.cidada@exemplo.com',
            'role': 'citizen',
            'created_at': '2026-11-19T15:00:00Z',
          },
        }),
        200,
      );
    });

    await http.runWithClient(() async {
      await _openApp(tester);
      for (final checkbox
          in tester.widgetList<Checkbox>(find.byType(Checkbox))) {
        checkbox.onChanged!(true);
      }
      await tester.pump();
      await tester.tap(find.text('Entrar com e-mail').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'ana.cidada@exemplo.com');
      await tester.tap(find.text('Enviar código'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), '123456');
      await tester.tap(find.text('Confirmar entrada'));
      await tester.pump(); // resposta da API e troca para o HomeShell
      await tester.pump(const Duration(seconds: 1)); // fim da transição
    }, () => api);

    expect(find.text('Olá, ana.cidada 👋'), findsOneWidget);
    expect(stored['reclame_ja_display_name'], 'ana.cidada');
    await unmount(tester);
  });

  test('logout clears the stored display name with the session', () async {
    final stored =
        _storage({..._tokens, 'reclame_ja_display_name': 'ana.cidada'});
    await SessionStore.restore();

    await SessionStore.clear();

    expect(SessionStore.displayName, isNull);
    expect(stored, isNot(contains('reclame_ja_display_name')));
  });
}
