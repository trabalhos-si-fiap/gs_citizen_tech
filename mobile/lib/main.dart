import 'package:flutter/material.dart';
import 'app_theme.dart';
import 'screens/home_shell.dart';
import 'screens/welcome_screen.dart';
import 'services/push_service.dart';
import 'services/session_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
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
          ? const HomeShell(isVisitor: false, userName: 'Munícipe')
          : const WelcomeScreen(),
    );
  }
}
