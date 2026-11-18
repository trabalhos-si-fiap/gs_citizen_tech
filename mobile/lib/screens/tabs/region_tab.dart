import 'package:flutter/material.dart';

import '../../app_theme.dart';
import '../../services/api_client.dart';

class RegionTab extends StatefulWidget {
  final bool isVisitor;

  const RegionTab({super.key, required this.isVisitor});

  @override
  State<RegionTab> createState() => _RegionTabState();
}

class _RegionTabState extends State<RegionTab> {
  Map<String, dynamic>? _metrics;
  Object? _loadError;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadMetrics();
  }

  Future<void> _loadMetrics() async {
    if (_isLoading) return;
    setState(() {
      _isLoading = true;
      _loadError = null;
    });
    try {
      final metrics = await ApiClient().getPublicMetrics();
      if (mounted) setState(() => _metrics = metrics);
    } catch (error) {
      if (mounted) setState(() => _loadError = error);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  String _formatHours(Object? value) {
    if (value is! num) return '—';
    return '${value.toStringAsFixed(1)} h';
  }

  String _formatRate(Object? value) {
    if (value is! num) return '—';
    return '${(value * 100).toStringAsFixed(1)}%';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    final totals = _metrics?['totals'] is Map
        ? Map<String, dynamic>.from(_metrics!['totals'] as Map)
        : const <String, dynamic>{};
    final agencies = (_metrics?['by_agency'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Feed da Região'),
        centerTitle: true,
        actions: [
          IconButton(
            onPressed: _isLoading ? null : _loadMetrics,
            icon: const Icon(Icons.refresh),
            tooltip: 'Atualizar indicadores',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadMetrics,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'Transparência & Métricas',
              style: theme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            if (_isLoading && _metrics == null)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (_loadError != null && _metrics == null)
              _buildError(context)
            else if (_metrics == null)
              const Text('Ainda não há indicadores disponíveis.')
            else ...[
              Row(
                children: [
                  _metricCard(
                    context,
                    label: 'Reportes',
                    value: '${totals['reports'] ?? 0}',
                    icon: Icons.assignment_outlined,
                    color: ReclameJaColors.tertiaryBlue,
                  ),
                  const SizedBox(width: 8),
                  _metricCard(
                    context,
                    label: 'Tempo médio',
                    value: _formatHours(totals['avg_response_hours']),
                    icon: Icons.timer_outlined,
                    color: ReclameJaColors.primaryYellow,
                  ),
                  const SizedBox(width: 8),
                  _metricCard(
                    context,
                    label: 'Resolvidos',
                    value: _formatRate(totals['resolution_rate']),
                    icon: Icons.check_circle_outline,
                    color: ReclameJaColors.secondaryEmerald,
                  ),
                ],
              ),
              const SizedBox(height: 24),
              Text(
                'Indicadores por órgão',
                style: theme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              if (agencies.isEmpty)
                const Text('Não há dados agregados disponíveis por órgão.')
              else
                ...agencies.map(_agencyCard),
              const SizedBox(height: 12),
              Text(
                'Indicadores agregados; grupos com poucos registros não são exibidos.',
                style: theme.bodySmall?.copyWith(
                  color: ReclameJaColors.textMuted,
                ),
              ),
            ],
            if (_loadError != null && _metrics != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  'A atualização falhou. Os últimos dados carregados permanecem visíveis.',
                  style: theme.bodySmall?.copyWith(
                    color: ReclameJaColors.alertRed,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _metricCard(
    BuildContext context, {
    required String label,
    required String value,
    required IconData icon,
    required Color color,
  }) {
    final theme = Theme.of(context).textTheme;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        decoration: BoxDecoration(
          color: ReclameJaColors.surfaceBright,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: ReclameJaColors.borderSlate),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(height: 8),
            Text(
              value,
              style: theme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            Text(
              label,
              style:
                  theme.labelSmall?.copyWith(color: ReclameJaColors.textMuted),
            ),
          ],
        ),
      ),
    );
  }

  Widget _agencyCard(Map<String, dynamic> item) {
    final agency = item['agency'] is Map
        ? Map<String, dynamic>.from(item['agency'] as Map)
        : const <String, dynamic>{};
    return Card(
      color: ReclameJaColors.surfaceBright,
      child: ListTile(
        title: Text(agency['name']?.toString() ?? 'Órgão'),
        subtitle: Text(
          '${item['reports'] ?? 0} reportes · '
          'tempo médio ${_formatHours(item['avg_response_hours'])}',
        ),
        trailing: Text(_formatRate(item['resolution_rate'])),
      ),
    );
  }

  Widget _buildError(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Column(
        children: [
          const Text('Não foi possível carregar os indicadores públicos.'),
          const SizedBox(height: 8),
          TextButton(
            onPressed: _loadMetrics,
            child: const Text('Tentar novamente'),
          ),
        ],
      ),
    );
  }
}
