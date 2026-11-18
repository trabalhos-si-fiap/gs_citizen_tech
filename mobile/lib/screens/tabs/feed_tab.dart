import 'package:flutter/material.dart';

import '../../app_theme.dart';
import '../../services/location_service.dart';
import '../../services/nearby_service.dart';
import '../report_detail_screen.dart';

/// Raio do feed "Perto de você", em metros.
const int feedRadiusM = 1000;

class FeedTab extends StatefulWidget {
  final bool isVisitor;
  final String userName;
  final NearbyStore? nearbyStore;
  final LocationService? locationService;

  const FeedTab({
    super.key,
    required this.isVisitor,
    required this.userName,
    this.nearbyStore,
    this.locationService,
  });

  @override
  State<FeedTab> createState() => _FeedTabState();
}

class _FeedTabState extends State<FeedTab> {
  String _activeFilter = 'Todos';
  GeoPoint? _center;

  late final NearbyStore _store = widget.nearbyStore ?? NearbyStore.shared;
  late final LocationService _location =
      widget.locationService ?? const DeviceLocationService();

  @override
  void initState() {
    super.initState();
    _store.addListener(_onStoreChanged);
    _refresh();
  }

  @override
  void dispose() {
    _store.removeListener(_onStoreChanged);
    super.dispose();
  }

  void _onStoreChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _refresh() async {
    final center = _center ??= await _location.current();
    await _store.load(
      latitude: center.latitude,
      longitude: center.longitude,
      radiusM: feedRadiusM,
      category: categoryForLabel(_activeFilter),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final reports = _store.items;

    return Scaffold(
      backgroundColor: ReclameJaColors.surfaceMain,
      appBar: AppBar(
        title: const Text('Feed'),
        centerTitle: true,
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: ReclameJaColors.borderSlate),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color:
                          ReclameJaColors.primaryYellow.withValues(alpha: 0.35),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.near_me,
                      color: ReclameJaColors.textDark,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Perto de você',
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _store.isLoading
                              ? 'Buscando ocorrências...'
                              : 'Raio de 1 km • ${reports.length} ocorrências',
                          style: textTheme.bodySmall?.copyWith(
                            color: ReclameJaColors.textMuted,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
            child: SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  _buildFilterChip('Todos', Icons.all_inclusive),
                  const SizedBox(width: 8),
                  _buildFilterChip('Risco Urbano', Icons.warning,
                      color: Colors.amber.shade700),
                  const SizedBox(width: 8),
                  _buildFilterChip('Transporte', Icons.directions_bus,
                      color: ReclameJaColors.tertiaryBlue),
                  const SizedBox(width: 8),
                  _buildFilterChip('Saúde', Icons.local_hospital,
                      color: ReclameJaColors.alertRed),
                ],
              ),
            ),
          ),
          const SizedBox(height: 6),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () {
                _center = null;
                return _refresh();
              },
              child: reports.isEmpty
                  ? ListView(children: [_buildEmptyState()])
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
                      itemCount: reports.length,
                      itemBuilder: (context, index) =>
                          _buildReportCard(reports[index]),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, IconData icon, {Color? color}) {
    final isSelected = _activeFilter == label;
    return FilterChip(
      selected: isSelected,
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != Icons.all_inclusive) ...[
            Icon(
              icon,
              size: 14,
              color: isSelected
                  ? ReclameJaColors.textDark
                  : (color ?? ReclameJaColors.textMuted),
            ),
            const SizedBox(width: 4),
          ],
          Text(label,
              style:
                  const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
        ],
      ),
      backgroundColor: ReclameJaColors.surfaceBright,
      selectedColor: ReclameJaColors.primaryYellow,
      showCheckmark: false,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: ReclameJaColors.borderSlate),
      ),
      onSelected: (_) {
        setState(() => _activeFilter = label);
        _refresh();
      },
    );
  }

  void _openDetail(NearbyReport report) {
    if (widget.isVisitor) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Entre na sua conta para ver detalhes e apoiar.'),
        ),
      );
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ReportDetailScreen(report: report.toReport()),
      ),
    );
  }

  Widget _buildReportCard(NearbyReport report) {
    final textTheme = Theme.of(context).textTheme;
    final isResolved = report.status == 'resolvido';
    final isInProgress = report.status == 'em_andamento';

    final Color statusColor;
    final Color statusBg;
    if (isResolved) {
      statusColor = ReclameJaColors.secondaryEmerald;
      statusBg = const Color(0xFFDCFCE7);
    } else if (isInProgress) {
      statusColor = Colors.amber.shade900;
      statusBg = const Color(0xFFFEF9C3);
    } else {
      statusColor = ReclameJaColors.onBlueContainer;
      statusBg = ReclameJaColors.blueContainer;
    }

    return Card(
      elevation: 1,
      margin: const EdgeInsets.only(bottom: 12),
      color: ReclameJaColors.surfaceBright,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: ReclameJaColors.borderSlate),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _openDetail(report),
        child: Padding(
          padding: const EdgeInsets.all(14.0),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(categoryIcon(report.category),
                    color: statusColor, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      report.categoryLabel,
                      style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(Icons.location_on,
                            size: 12, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          report.distanceLabel,
                          style: textTheme.bodySmall
                              ?.copyWith(color: ReclameJaColors.textMuted),
                        ),
                        const SizedBox(width: 12),
                        const Icon(Icons.thumb_up_alt_outlined,
                            size: 12, color: ReclameJaColors.secondaryEmerald),
                        const SizedBox(width: 4),
                        Text(
                          '${report.confirmationCount}',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: ReclameJaColors.secondaryEmerald,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  report.statusLabel,
                  style: TextStyle(
                      color: statusColor,
                      fontSize: 10,
                      fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    final textTheme = Theme.of(context).textTheme;
    final failed = _store.error != null;
    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        children: [
          Icon(failed ? Icons.cloud_off : Icons.location_city_outlined,
              size: 56, color: ReclameJaColors.surfaceDim),
          const SizedBox(height: 16),
          Text(
            failed ? 'Sem conexão com o servidor' : 'Nenhum chamado por perto',
            style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            failed
                ? 'Puxe para baixo para tentar novamente.'
                : 'Não há ocorrências públicas nesta categoria no raio de 1 km.',
            style:
                textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

IconData categoryIcon(String? category) => switch (category) {
      'transporte_publico' => Icons.directions_bus,
      'saude_atendimento' => Icons.local_hospital,
      'risco_urbano' => Icons.warning,
      _ => Icons.help_outline,
    };
