import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';
import '../services/report_store.dart';
import 'report_detail_screen.dart';

class PostSendConfirmationScreen extends StatefulWidget {
  final Report report;

  const PostSendConfirmationScreen({super.key, required this.report});

  @override
  State<PostSendConfirmationScreen> createState() => _PostSendConfirmationScreenState();
}

class _PostSendConfirmationScreenState extends State<PostSendConfirmationScreen> {
  bool _isConfirmedByMunicipe = false;

  void _confirmData() {
    setState(() {
      _isConfirmedByMunicipe = true;
    });
    
    // Add positive tracking event in timeline
    final event = ReportEvent(
      title: 'Classificação Confirmada',
      time: '16/11 às 17:05',
      desc: 'Matriz de encaminhamento re-validada pelo cidadão.',
      actor: 'Marina (Você)',
    );
    ReportStore().updateReportStatus(widget.report.id, 'Recebido', event);

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Dados validados com sucesso pelo munícipe!'),
        backgroundColor: ReclameJaColors.secondaryEmerald,
      ),
    );
  }

  void _correctData() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Corrigir Dados', style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
        content: Text(
          'Modo de edição: você gostaria de alterar a classificação recomendada para outra categoria da matriz?',
          style: GoogleFonts.hankenGrotesk(),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar', style: TextStyle(color: ReclameJaColors.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: ReclameJaColors.primaryYellow,
              foregroundColor: ReclameJaColors.textDark,
            ),
            onPressed: () {
              Navigator.pop(context);
              // Toggle category in store to demonstrate edit ability
              final updatedEvent = ReportEvent(
                title: 'Categoria Retificada',
                time: '16/11 às 17:05',
                desc: 'Categoria e Órgão de destino alterados manualmente pelo cidadão de "Pavimentação" para "Drenagem".',
                actor: 'Marina (Você)',
              );
              ReportStore().updateReportStatus(widget.report.id, 'Recebido', updatedEvent);
              
              setState(() {
                _isConfirmedByMunicipe = true;
              });

              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Classificação retificada com sucesso!'),
                  backgroundColor: ReclameJaColors.secondaryEmerald,
                ),
              );
            },
            child: const Text('Alterar categoria'),
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
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('Confirmação'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header Section
            Center(
              child: Column(
                children: [
                  Stack(
                    alignment: Alignment.bottomRight,
                    children: [
                      Container(
                        width: 64,
                        height: 64,
                        decoration: BoxDecoration(
                          color: const Color(0xFFDCFCE7),
                          shape: BoxShape.circle,
                          border: Border.all(color: const Color(0xFF86EFAC)),
                        ),
                        child: const Icon(Icons.task_alt, color: Color(0xFF16A34A), size: 34),
                      ),
                      Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          color: const Color(0xFF16A34A),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                        child: const Icon(Icons.check, color: Colors.white, size: 14),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Protocol Badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFFDCFCE7),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: const Color(0xFF86EFAC)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.tag, size: 14, color: Color(0xFF14532D)),
                        const SizedBox(width: 4),
                        Text(
                          'Protocolo ${widget.report.id}',
                          style: textTheme.labelSmall?.copyWith(
                            color: const Color(0xFF14532D),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Entendemos o seu reporte',
                    style: textTheme.displayMedium?.copyWith(fontSize: 26, fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Nossa IA analisou a imagem e os dados para direcionar ao setor correto da prefeitura.',
                    style: textTheme.bodyMedium?.copyWith(color: ReclameJaColors.textMuted),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // AI Triage Review Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: ReclameJaColors.borderSlate),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 6,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Photo preview in triage card
                  Container(
                    height: 140,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      color: ReclameJaColors.surfaceLow,
                      image: widget.report.imageUrl != null
                          ? DecorationImage(
                              image: NetworkImage(widget.report.imageUrl!),
                              fit: BoxFit.cover,
                            )
                          : null,
                    ),
                    child: Stack(
                      children: [
                        if (widget.report.imageUrl == null)
                          const Center(
                            child: Icon(Icons.photo, size: 48, color: ReclameJaColors.textMuted),
                          ),
                        Positioned(
                          top: 10,
                          right: 10,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.95),
                              borderRadius: BorderRadius.circular(999),
                              border: Border.all(color: const Color(0xFF86EFAC)),
                            ),
                            child: const Row(
                              children: [
                                Icon(Icons.verified, color: Color(0xFF16A34A), size: 14),
                                SizedBox(width: 4),
                                Text(
                                  'Análise concluída',
                                  style: TextStyle(color: Color(0xFF16A34A), fontSize: 11, fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                          ),
                        ),
                        Positioned(
                          bottom: 10,
                          left: 10,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.7),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.location_on, color: Colors.white, size: 14),
                                const SizedBox(width: 4),
                                Text(
                                  widget.report.location,
                                  style: const TextStyle(color: Colors.white, fontSize: 11),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Smart Classification Badge
                  Row(
                    children: [
                      const Icon(Icons.auto_fix_high, size: 16, color: ReclameJaColors.secondaryEmerald),
                      const SizedBox(width: 6),
                      Text('Classificação Inteligente', style: textTheme.labelSmall?.copyWith(color: ReclameJaColors.textMuted)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: ReclameJaColors.surfaceLow,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: ReclameJaColors.surfaceDim.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: const BoxDecoration(
                            color: Color(0xFFDCFCE7),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.construction, color: Color(0xFF16A34A), size: 20),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${widget.report.category} • ${widget.report.subcategory}',
                                style: textTheme.labelLarge?.copyWith(fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Buraco ou desnível verificado na malha viária.',
                                style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Severity Indicators
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Severidade Detectada', style: textTheme.labelSmall?.copyWith(color: ReclameJaColors.textMuted)),
                      Text(
                        'Média-Alta (Risco Preventivo)',
                        style: textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Expanded(child: Container(height: 6, decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: Colors.amber.shade300))),
                      const SizedBox(width: 6),
                      Expanded(child: Container(height: 6, decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: Colors.amber.shade500))),
                      const SizedBox(width: 6),
                      Expanded(child: Container(height: 6, decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: ReclameJaColors.surfaceDim))),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Impacto identificado no tráfego local e circulação de pedestres.',
                    style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                  ),
                  const SizedBox(height: 16),

                  // Destination Department Card
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF0FDF4),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFF86EFAC).withValues(alpha: 0.8)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.account_balance, color: Color(0xFF16A34A), size: 22),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Destino do Chamado',
                                style: textTheme.labelSmall?.copyWith(color: const Color(0xFF15803D), fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                widget.report.organ,
                                style: textTheme.labelLarge?.copyWith(fontSize: 13, fontWeight: FontWeight.bold, height: 1.3),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Validation Action Blocks
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Center(
                        child: Text(
                          'As informações correspondem ao problema?',
                          style: textTheme.bodyMedium,
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (!_isConfirmedByMunicipe)
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: ReclameJaColors.textDark,
                                  side: const BorderSide(color: ReclameJaColors.borderSlate),
                                  minimumSize: const Size.fromHeight(48),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                ),
                                onPressed: _correctData,
                                icon: const Icon(Icons.edit, size: 16),
                                label: const Text('Corrigir dados', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: ReclameJaColors.primaryYellow,
                                  foregroundColor: ReclameJaColors.textDark,
                                  minimumSize: const Size.fromHeight(48),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                ),
                                onPressed: _confirmData,
                                icon: const Icon(Icons.thumb_up_alt_outlined, size: 16),
                                label: const Text('Sim, confirmar', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                              ),
                            ),
                          ],
                        )
                      else
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFDCFCE7),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: const Color(0xFF86EFAC)),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.check_circle, color: Color(0xFF16A34A), size: 20),
                              const SizedBox(width: 8),
                              Text(
                                'Dados validados com sucesso!',
                                style: textTheme.labelMedium?.copyWith(
                                  color: const Color(0xFF14532D),
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // What happens next timeline card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: ReclameJaColors.borderSlate),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('O que vai acontecer agora', style: textTheme.titleMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFDCFCE7),
                          borderRadius: BorderRadius.circular(99),
                        ),
                        child: Row(
                          children: [
                            Container(width: 5, height: 5, decoration: const BoxDecoration(color: Color(0xFF16A34A), shape: BoxShape.circle)),
                            const SizedBox(width: 4),
                            Text(
                              'Em fluxo',
                              style: textTheme.labelSmall?.copyWith(color: const Color(0xFF16A34A), fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildTimelineItem(
                    icon: Icons.assignment_turned_in_outlined,
                    stepTitle: '1. Encaminhamento oficial',
                    timeLabel: '2h',
                    description: 'Inclusão no sistema central de zeladoria e agendamento na base técnica distrital.',
                    isDone: true,
                  ),
                  _buildTimelineItem(
                    icon: Icons.engineering_outlined,
                    stepTitle: '2. Vistoria técnica',
                    timeLabel: '48h úteis',
                    description: 'Equipe de campo avalia a extensão do dano e emite a ordem de serviço operacional.',
                    isDone: false,
                  ),
                  _buildTimelineItem(
                    icon: Icons.notifications_active_outlined,
                    stepTitle: '3. Notificações diretas',
                    timeLabel: 'Tempo real',
                    description: 'Receba fotos de vistoria, início das obras e o registro da conclusão do reparo.',
                    isDone: false,
                    isLast: true,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Engaged Neighbors box
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceLow,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: const BoxDecoration(
                      color: ReclameJaColors.surfaceBright,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.share_location, color: ReclameJaColors.secondaryEmerald, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Vizinhos engajados', style: textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 2),
                        Text(
                          '3 moradores reforçaram a urgência deste local nas últimas 48h.',
                          style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Footer navigation buttons
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: ReclameJaColors.primaryYellow,
                foregroundColor: ReclameJaColors.textDark,
                minimumSize: const Size.fromHeight(52),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () {
                // Find Report in Store to get latest state and navigate
                final latestReport = ReportStore().allReports.firstWhere(
                  (r) => r.id == widget.report.id,
                  orElse: () => widget.report,
                );
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => ReportDetailScreen(report: latestReport),
                  ),
                );
              },
              icon: const Icon(Icons.receipt_long, size: 20),
              label: const Text('Acompanhar chamado', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () {
                // Back to main tab screen (pop back to HomeShell)
                Navigator.of(context).popUntil((route) => route.isFirst);
              },
              child: Text(
                'Voltar ao início',
                style: textTheme.labelLarge?.copyWith(color: ReclameJaColors.secondaryEmerald, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildTimelineItem({
    required IconData icon,
    required String stepTitle,
    required String timeLabel,
    required String description,
    required bool isDone,
    bool isLast = false,
  }) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: isDone ? const Color(0xFFDCFCE7) : ReclameJaColors.surfaceLow,
                  shape: BoxShape.circle,
                  border: Border.all(color: isDone ? const Color(0xFF86EFAC) : ReclameJaColors.borderSlate),
                ),
                child: Icon(icon, size: 16, color: isDone ? const Color(0xFF16A34A) : ReclameJaColors.textMuted),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: ReclameJaColors.borderSlate,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 16.0, top: 4.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(stepTitle, style: GoogleFonts.hankenGrotesk(fontSize: 14, fontWeight: FontWeight.bold)),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                        decoration: BoxDecoration(
                          color: ReclameJaColors.surfaceLow,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(timeLabel, style: GoogleFonts.hankenGrotesk(fontSize: 10, color: ReclameJaColors.textMuted)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: GoogleFonts.hankenGrotesk(fontSize: 12, color: ReclameJaColors.textMuted, height: 1.3),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
