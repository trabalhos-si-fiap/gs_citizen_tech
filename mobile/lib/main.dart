import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_theme.dart';

void main() {
  runApp(const ReclameJaApp());
}

class ReclameJaApp extends StatelessWidget {
  const ReclameJaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Reclame Já',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme(),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ReclameJaColors.surfaceMain,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                decoration: BoxDecoration(
                  color: ReclameJaColors.primaryYellow,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Reclame Já',
                  style: GoogleFonts.poppins(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: ReclameJaColors.textDeep,
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Identidade visual unificada',
                style: GoogleFonts.poppins(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: ReclameJaColors.textDark,
                ),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceBright,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: ReclameJaColors.surfaceDim),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _ColorChip(
                      label: 'Amarelo',
                      color: ReclameJaColors.primaryYellow,
                    ),
                    const SizedBox(width: 12),
                    _ColorChip(
                      label: 'Verde',
                      color: ReclameJaColors.primaryGreen,
                    ),
                    const SizedBox(width: 12),
                    _ColorChip(
                      label: 'Alerta',
                      color: ReclameJaColors.alertRed,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ColorChip extends StatelessWidget {
  const _ColorChip({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: ReclameJaColors.textDark.withValues(alpha: 0.12),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          label,
          style: GoogleFonts.poppins(
            fontSize: 11,
            fontWeight: FontWeight.w500,
            color: ReclameJaColors.textDark,
          ),
        ),
      ],
    );
  }
}
