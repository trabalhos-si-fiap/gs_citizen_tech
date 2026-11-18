import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';

class EmergencyScreen extends StatelessWidget {
  const EmergencyScreen({super.key});

  void _callNumber(BuildContext context, String title, String number) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Chamada de Emergência',
            style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
        content: Text(
            'Dispositivo simulando chamada de suporte para $title ($number).'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Desconectar',
                style: TextStyle(color: ReclameJaColors.alertRed)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Canais de Emergência'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Warning Spotlight Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF101828),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: const BoxDecoration(
                      color: ReclameJaColors.primaryYellow,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.emergency,
                        color: ReclameJaColors.textDark, size: 32),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Risco imediato à vida?',
                    style: GoogleFonts.spaceGrotesk(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Este aplicativo é destinado exclusivamente a manutenções urbanas programadas. Ele NÃO é um canal de denúncia de crimes em andamento nem um botão de pânico.',
                    style: GoogleFonts.hankenGrotesk(
                      color: Colors.white.withValues(alpha: 0.9),
                      fontSize: 14,
                      height: 1.4,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            Text(
              'Contatos Rápidos de Socorro Vital',
              style:
                  textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),

            // 190 button
            _buildBigDialButton(
              context,
              icon: Icons.shield,
              title: 'POLÍCIA MILITAR',
              number: '190',
              description:
                  'Para ocorrências de crimes ativos, roubos, perturbação grave de sossego ou acidentes com violência.',
              color: Colors.blue.shade900,
            ),
            const SizedBox(height: 12),

            // 192 button
            _buildBigDialButton(
              context,
              icon: Icons.local_hospital,
              title: 'SAMU - SUPORTE DE SAÚDE',
              number: '192',
              description:
                  'Para socorro de urgências médicas de saúde, acidentes com feridos, infartos ou partos imediatos.',
              color: ReclameJaColors.alertRed,
            ),
            const SizedBox(height: 12),

            // 193 button
            _buildBigDialButton(
              context,
              icon: Icons.local_fire_department,
              title: 'CORPO DE BOMBEIROS',
              number: '193',
              description:
                  'Para incêndios ativos, vazamentos de gás perigosos, resgate de vítimas presas em ferragens ou desabamentos.',
              color: Colors.orange.shade800,
            ),
            const SizedBox(height: 24),

            // Warning note card
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceLow,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.info,
                          size: 14, color: ReclameJaColors.textMuted),
                      const SizedBox(width: 6),
                      Text(
                        'Importância da Prevenção',
                        style: textTheme.labelSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: ReclameJaColors.textMuted),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'A segurança comunitária preventiva (postes de luz apagados, bueiros rompidos, árvores de risco) deve ser encaminhada via reporte de zeladoria comum para triagem operacional.',
                    style: textTheme.bodySmall?.copyWith(
                        color: ReclameJaColors.textMuted, height: 1.4),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBigDialButton(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String number,
    required String description,
    required Color color,
  }) {
    return Card(
      elevation: 1,
      color: ReclameJaColors.surfaceBright,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: ReclameJaColors.borderSlate),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _callNumber(context, title, number),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          title,
                          style: GoogleFonts.spaceGrotesk(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: ReclameJaColors.textDark,
                          ),
                        ),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: color,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            number,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: GoogleFonts.hankenGrotesk(
                        fontSize: 11,
                        color: ReclameJaColors.textMuted,
                        height: 1.3,
                      ),
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
