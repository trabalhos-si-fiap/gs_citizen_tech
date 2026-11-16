import 'package:flutter/material.dart';
import 'app_theme.dart';
import 'screens/welcome_screen.dart';

void main() {
  runApp(const ReclameJaApp());
}

class ReclameJaApp extends StatelessWidget {
  const ReclameJaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Voz Cidadã',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme(),
      home: const WelcomeScreen(),
    );
  }
}
