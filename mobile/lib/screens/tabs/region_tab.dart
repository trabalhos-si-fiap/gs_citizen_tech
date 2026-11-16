import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../app_theme.dart';

class RegionTab extends StatelessWidget {
  final bool isVisitor;

  const RegionTab({super.key, required this.isVisitor});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Feed da Região'),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Section 1: Dashboard Public Metrics
            Text(
              'Transparência & Métricas',
              style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            
            // Grid of 3 key public metrics (similar to painel-de-dados.html)
            Row(
              children: [
                _buildMetricCard(
                  context,
                  label: 'Tempo Médio',
                  value: '44h',
                  sub: 'de resposta técnica',
                  icon: Icons.timer,
                  color: ReclameJaColors.tertiaryBlue,
                ),
                const SizedBox(width: 8),
                _buildMetricCard(
                  context,
                  label: 'Resolução',
                  value: '92.5%',
                  sub: 'de chamados fechados',
                  icon: Icons.check_circle,
                  color: ReclameJaColors.secondaryEmerald,
                ),
                const SizedBox(width: 8),
                _buildMetricCard(
                  context,
                  label: 'Total Distrital',
                  value: '142',
                  sub: 'reportes registrados',
                  icon: Icons.assignment,
                  color: ReclameJaColors.primaryYellow,
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Section 2: Visual Charts (Resolution Rate by Category)
            Text(
              'Distribuição por Categoria',
              style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: ReclameJaColors.borderSlate),
              ),
              child: Column(
                children: [
                  _buildChartRow(
                    category: 'Risco Urbano',
                    percentage: 0.65,
                    color: Colors.amber.shade600,
                    count: '92',
                  ),
                  const SizedBox(height: 12),
                  _buildChartRow(
                    category: 'Transporte Público',
                    percentage: 0.25,
                    color: ReclameJaColors.tertiaryBlue,
                    count: '35',
                  ),
                  const SizedBox(height: 12),
                  _buildChartRow(
                    category: 'Saúde (Zeladoria)',
                    percentage: 0.10,
                    color: ReclameJaColors.alertRed,
                    count: '15',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Section 3: Neighborhood feed (community tracking)
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Atividades Recentes',
                  style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: ReclameJaColors.surfaceLow,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.location_on, size: 12, color: ReclameJaColors.secondaryEmerald),
                      SizedBox(width: 4),
                      Text('Jardim das Flores', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Feed Item 1 (Resolved pothole)
            _buildFeedCard(
              title: 'Lâmpadas substituídas na Praça da Matriz',
              location: 'Praça da Matriz, Lado Leste',
              status: 'RESOLVIDO',
              statusColor: ReclameJaColors.secondaryEmerald,
              statusBg: const Color(0xFFDCFCE7),
              photoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAteX67nFZrT7fEmVMHwiRPnpQlxUg1QjzJ4ZuW_EeivJSZmDQGw2_XCp3841SGDhksCrogHwdGhQt3wVBOaa5rhC7YMzqUOYYyp4IwBEdbMH2IxrMGhxCi-8sYCvuqlrUJaEtJvHrJIWpcTivi-1-7tpOIs7VbWAz31DZD9MkQKoqmuU8av2kKMP7oEEb10GvFz4l4prL77Ojjs6qCrPIB9ZTYwCH_TLVjJYRlPS_b',
              description: 'Três pontos de luz que se encontravam apagados há dias foram reparados e substituídos por lâmpadas de LED potentes pela prefeitura.',
              timeLabel: 'Concluído há 4h',
              supportsCount: 23,
            ),
            const SizedBox(height: 12),

            // Feed Item 2 (Poda em andamento)
            _buildFeedCard(
              title: 'Poda de árvore gigante com risco elétrico',
              location: 'Rua das Acácias, 450',
              status: 'EM ANDAMENTO',
              statusColor: Colors.amber.shade900,
              statusBg: const Color(0xFFFEF9C3),
              photoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCIe4nA0gwvKNtMa9Zt8wmPBk8EQDNw3_keZlUqoHaQ4UfsLnJ3GyTyJh2sLgomyhQMoNVdKozxKhDPoho6ahRq132VhCJCqLE79r-jxEEi5fFOOWjsFdWidSPNxQLv2FxbDZFQwG8nwPnJde0MDrgkeS6r20meg8c_VJA2Zg3DAo3IyPuMk46_FGYHSQWXj540cNotDDLaapBQuGeAFVEElVDOe9nEhLrr2BBuypov',
              description: 'Uma equipe de zeladoria foi despachada para vistoria e sinalização. Aguardando corte dos galhos que tocam a rede de alta tensão.',
              timeLabel: 'Atualizado ontem',
              supportsCount: 14,
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(
    BuildContext context, {
    required String label,
    required String value,
    required String sub,
    required IconData icon,
    required Color color,
  }) {
    final textTheme = Theme.of(context).textTheme;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        decoration: BoxDecoration(
          color: ReclameJaColors.surfaceBright,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: ReclameJaColors.borderSlate),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.02),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: color, size: 16),
            ),
            const SizedBox(height: 10),
            Text(
              value,
              style: GoogleFonts.spaceGrotesk(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: ReclameJaColors.textDark,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: textTheme.labelSmall?.copyWith(fontWeight: FontWeight.bold, fontSize: 10),
            ),
            const SizedBox(height: 1),
            Text(
              sub,
              style: textTheme.bodySmall?.copyWith(fontSize: 9, color: ReclameJaColors.textMuted, height: 1.2),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChartRow({
    required String category,
    required double percentage,
    required Color color,
    required String count,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              category,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: ReclameJaColors.textDark),
            ),
            Text(
              '$count chamados (${(percentage * 100).toInt()}%)',
              style: const TextStyle(fontSize: 11, color: ReclameJaColors.textMuted, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              flex: (percentage * 100).toInt(),
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            Expanded(
              flex: (100 - (percentage * 100)).toInt(),
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildFeedCard({
    required String title,
    required String location,
    required String status,
    required Color statusColor,
    required Color statusBg,
    required String photoUrl,
    required String description,
    required String timeLabel,
    required int supportsCount,
  }) {
    return Card(
      elevation: 1,
      color: ReclameJaColors.surfaceBright,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: ReclameJaColors.borderSlate),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Row 1: Header title
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: ReclameJaColors.textDark),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          const Icon(Icons.location_on, size: 10, color: ReclameJaColors.textMuted),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              location,
                              style: const TextStyle(fontSize: 11, color: ReclameJaColors.textMuted),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusBg,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(color: statusColor, fontSize: 9, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),

          // Image block
          Container(
            height: 120,
            decoration: BoxDecoration(
              image: DecorationImage(
                image: NetworkImage(photoUrl),
                fit: BoxFit.cover,
              ),
            ),
          ),

          // Description block
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  description,
                  style: const TextStyle(fontSize: 12, color: ReclameJaColors.textMuted, height: 1.3),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 10),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      timeLabel,
                      style: const TextStyle(fontSize: 11, color: ReclameJaColors.textMuted),
                    ),
                    Row(
                      children: [
                        const Icon(Icons.thumb_up_alt_outlined, size: 12, color: ReclameJaColors.secondaryEmerald),
                        const SizedBox(width: 4),
                        Text(
                          '$supportsCount apoios',
                          style: const TextStyle(fontSize: 11, color: ReclameJaColors.secondaryEmerald, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
