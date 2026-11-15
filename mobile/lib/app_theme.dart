import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class ReclameJaColors {
  static const primaryYellow = Color(0xFFEBE100);
  static const primaryGreen = Color(0xFF22C55E);
  static const primaryGreenSoft = Color(0xFF4ADE80);
  static const alertRed = Color(0xFFEF4444);
  static const surfaceMain = Color(0xFFF9F9FC);
  static const surfaceBright = Color(0xFFFFFFFF);
  static const surfaceLow = Color(0xFFF3F3F6);
  static const surfaceDim = Color(0xFFDADADC);
  static const textDark = Color(0xFF1A1C1E);
  static const textDeep = Color(0xFF1E1C00);
}

class AppTheme {
  static ThemeData lightTheme() {
    final baseTheme = ThemeData.light(useMaterial3: true);

    return baseTheme.copyWith(
      scaffoldBackgroundColor: ReclameJaColors.surfaceMain,
      primaryColor: ReclameJaColors.primaryYellow,
      colorScheme: const ColorScheme(
        brightness: Brightness.light,
        primary: ReclameJaColors.primaryYellow,
        onPrimary: ReclameJaColors.textDeep,
        secondary: ReclameJaColors.primaryGreen,
        onSecondary: ReclameJaColors.surfaceBright,
        error: ReclameJaColors.alertRed,
        onError: ReclameJaColors.surfaceBright,
        surface: ReclameJaColors.surfaceMain,
        onSurface: ReclameJaColors.textDark,
      ),
      textTheme: GoogleFonts.poppinsTextTheme(baseTheme.textTheme).apply(
        bodyColor: ReclameJaColors.textDark,
        displayColor: ReclameJaColors.textDeep,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: ReclameJaColors.surfaceMain,
        foregroundColor: ReclameJaColors.textDeep,
        elevation: 0,
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: ReclameJaColors.primaryYellow,
        foregroundColor: ReclameJaColors.textDeep,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: ReclameJaColors.primaryYellow,
          foregroundColor: ReclameJaColors.textDeep,
          textStyle: GoogleFonts.poppins(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
