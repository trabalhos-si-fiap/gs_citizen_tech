import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_theme.dart';
import 'screens/home_shell.dart';
import 'screens/welcome_screen.dart';
import 'services/push_service.dart';
import 'services/session_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await preloadThemeFonts();
  await SessionStore.restore();
  if (SessionStore.accessToken != null) {
    try {
      await PushService.initializeAfterLogin();
    } catch (error) {
      debugPrint('Falha ao inicializar notificações: $error');
    }
  }
  runApp(
    ReclameJaApp(
      isAuthenticated: SessionStore.accessToken != null,
    ),
  );
}

/// Carrega as fontes do tema (Google Fonts) antes do primeiro frame.
///
/// Sem isso o primeiro frame sai com a fonte do sistema, mais estreita, e
/// widgets que medem o texto uma única vez (como os chips de filtro) guardam
/// essa largura e cortam o rótulo quando a fonte real chega. O tempo é
/// limitado para o app não travar sem rede na primeira abertura, quando a
/// fonte ainda precisa ser baixada.
Future<void> preloadThemeFonts({
  Duration timeout = const Duration(seconds: 3),
}) async {
  AppTheme.lightTheme(); // cria os estilos do tema e dispara o carregamento
  try {
    await GoogleFonts.pendingFonts().timeout(timeout);
  } catch (error) {
    debugPrint('Fontes do tema não carregaram a tempo: $error');
  }
}

class ReclameJaApp extends StatelessWidget {
  final bool isAuthenticated;

  const ReclameJaApp({super.key, this.isAuthenticated = false});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Voz Cidadã',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme(),
      home: isAuthenticated
          ? HomeShell(
              isVisitor: false,
              userName: SessionStore.displayName ?? 'Munícipe',
            )
          : const WelcomeScreen(),
    );
  }
}
