import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class ReclameJaColors {
  static const primaryYellow = Color(0xFFEBE100);
  static const secondaryEmerald = Color(0xFF15803D);
  static const tertiaryBlue = Color(0xFF0284C7);
  static const textDark = Color(0xFF1A1C1E);
  static const textMuted = Color(0xFF57606A);
  static const surfaceMain = Color(0xFFF9F9FC);
  static const surfaceBright = Color(0xFFFFFFFF);
  static const surfaceLow = Color(0xFFF3F3F6);
  static const surfaceDim = Color(0xFFDADADC);
  static const borderSlate = Color(0xFFE2E8F0);
  static const alertRed = Color(0xFFBA1A1A);
  static const errorContainer = Color(0xFFFFDAD6);
  static const onErrorContainer = Color(0xFF93000A);
  static const greenContainer = Color(0xFFDCFCE7);
  static const onGreenContainer = Color(0xFF14532D);
  static const amberContainer = Color(0xFFFEF9C3);
  static const onAmberContainer = Color(0xFF854D0E);
  static const blueContainer = Color(0xFFE0F2FE);
  static const onBlueContainer = Color(0xFF0369A1);
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
        onPrimary: ReclameJaColors.textDark,
        secondary: ReclameJaColors.secondaryEmerald,
        onSecondary: ReclameJaColors.surfaceBright,
        tertiary: ReclameJaColors.tertiaryBlue,
        onTertiary: ReclameJaColors.surfaceBright,
        error: ReclameJaColors.alertRed,
        onError: ReclameJaColors.surfaceBright,
        surface: ReclameJaColors.surfaceMain,
        onSurface: ReclameJaColors.textDark,
        outline: ReclameJaColors.borderSlate,
      ),
      // Set up the typographic scale using Space Grotesk for Headlines/Display,
      // Hanken Grotesk for Body/Title, and JetBrains Mono for metadata.
      textTheme: TextTheme(
        displayLarge: GoogleFonts.spaceGrotesk(
          fontSize: 48,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.02,
          color: ReclameJaColors.textDark,
        ),
        displayMedium: GoogleFonts.spaceGrotesk(
          fontSize: 36,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.02,
          color: ReclameJaColors.textDark,
        ),
        headlineLarge: GoogleFonts.spaceGrotesk(
          fontSize: 32,
          fontWeight: FontWeight.bold,
          letterSpacing: -0.01,
          color: ReclameJaColors.textDark,
        ),
        headlineMedium: GoogleFonts.spaceGrotesk(
          fontSize: 24,
          fontWeight: FontWeight.w600,
          color: ReclameJaColors.textDark,
        ),
        headlineSmall: GoogleFonts.spaceGrotesk(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: ReclameJaColors.textDark,
        ),
        titleLarge: GoogleFonts.hankenGrotesk(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: ReclameJaColors.textDark,
        ),
        titleMedium: GoogleFonts.hankenGrotesk(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: ReclameJaColors.textDark,
        ),
        bodyLarge: GoogleFonts.hankenGrotesk(
          fontSize: 16,
          fontWeight: FontWeight.normal,
          color: ReclameJaColors.textDark,
        ),
        bodyMedium: GoogleFonts.hankenGrotesk(
          fontSize: 14,
          fontWeight: FontWeight.normal,
          color: ReclameJaColors.textDark,
        ),
        bodySmall: GoogleFonts.hankenGrotesk(
          fontSize: 12,
          fontWeight: FontWeight.normal,
          color: ReclameJaColors.textDark,
        ),
        labelLarge: GoogleFonts.jetBrainsMono(
          fontSize: 13,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.02,
          color: ReclameJaColors.textDark,
        ),
        labelMedium: GoogleFonts.jetBrainsMono(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.04,
          color: ReclameJaColors.textDark,
        ),
        labelSmall: GoogleFonts.jetBrainsMono(
          fontSize: 10,
          fontWeight: FontWeight.w500,
          letterSpacing: 0.06,
          color: ReclameJaColors.textDark,
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: ReclameJaColors.surfaceMain,
        foregroundColor: ReclameJaColors.textDark,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleTextStyle: GoogleFonts.spaceGrotesk(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: ReclameJaColors.textDark,
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: ReclameJaColors.primaryYellow,
        foregroundColor: ReclameJaColors.textDark,
        elevation: 4,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: ReclameJaColors.secondaryEmerald,
          foregroundColor: ReclameJaColors.surfaceBright,
          minimumSize: const Size.fromHeight(52),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8), // rounded: 0.5rem (8px)
          ),
          textStyle: GoogleFonts.hankenGrotesk(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: ReclameJaColors.surfaceBright,
        hintStyle: GoogleFonts.hankenGrotesk(
          color: const Color(0xFF64748B),
          fontSize: 14,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFFCBD5E1), width: 1.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFFCBD5E1), width: 1.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: ReclameJaColors.secondaryEmerald, width: 2.0),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: ReclameJaColors.alertRed, width: 1.5),
        ),
      ),
    );
  }
}
