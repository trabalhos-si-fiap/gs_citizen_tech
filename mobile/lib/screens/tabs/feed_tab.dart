import 'package:flutter/material.dart';
import '../../app_theme.dart';
import '../../services/report_store.dart';
import '../report_detail_screen.dart';

class FeedTab extends StatefulWidget {
  final bool isVisitor;
  final String userName;

  const FeedTab({
    super.key,
    required this.isVisitor,
    required this.userName,
  });

  @override
  State<FeedTab> createState() => _FeedTabState();
}

class _FeedTabState extends State<FeedTab> {
  String _activeFilter = 'Todos';
  List<Report> _reportsList = [];

  @override
  void initState() {
    super.initState();
    _reportsList = ReportStore().allReports;
    _listenToStore();
  }

  void _listenToStore() {
    ReportStore().reportsStream.listen((list) {
      if (mounted) {
        setState(() {
          _reportsList = list;
        });
      }
    });
  }

  List<Report> _getFilteredReports() {
    if (_activeFilter == 'Todos') {
      return _reportsList;
    }
    return _reportsList.where((r) => r.category == _activeFilter).toList();
  }

  int _getCategoryCount(String cat) {
    if (cat == 'Todos') {
      return _reportsList.length;
    }
    return _reportsList.where((r) => r.category == cat).toList().length;
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final filteredReports = _getFilteredReports();

    return Scaffold(
      backgroundColor: ReclameJaColors.surfaceMain,
      appBar: AppBar(
        title: const Text('Feed'),
        centerTitle: true,
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header / Location & Summary info
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
                      color: ReclameJaColors.primaryYellow.withValues(alpha: 0.35),
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
                        Row(
                          children: [
                            Container(
                              width: 7,
                              height: 7,
                              decoration: const BoxDecoration(
                                color: Colors.green,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                'Raio de 800m • ${filteredReports.length} ocorrências no bairro',
                                style: textTheme.bodySmall?.copyWith(
                                  color: ReclameJaColors.textMuted,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Horizontal Category Filter Chips
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
            child: SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  _buildFilterChip('Todos', Icons.all_inclusive),
                  const SizedBox(width: 8),
                  _buildFilterChip('Risco Urbano', Icons.warning, color: Colors.amber.shade700),
                  const SizedBox(width: 8),
                  _buildFilterChip('Transporte', Icons.directions_bus, color: ReclameJaColors.tertiaryBlue),
                  const SizedBox(width: 8),
                  _buildFilterChip('Saúde', Icons.local_hospital, color: ReclameJaColors.alertRed),
                ],
              ),
            ),
          ),

          const SizedBox(height: 6),

          // Feed List
          Expanded(
            child: filteredReports.isEmpty
                ? _buildEmptyState()
                : RefreshIndicator(
                    onRefresh: () async {
                      setState(() {
                        _reportsList = ReportStore().allReports;
                      });
                    },
                    child: ListView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
                      itemCount: filteredReports.length,
                      itemBuilder: (context, index) {
                        return _buildReportCard(filteredReports[index]);
                      },
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, IconData icon, {Color? color}) {
    final isSelected = _activeFilter == label;
    final count = _getCategoryCount(label);

    return FilterChip(
      selected: isSelected,
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != Icons.all_inclusive) ...[
            Icon(
              icon,
              size: 14,
              color: isSelected ? ReclameJaColors.textDark : (color ?? ReclameJaColors.textMuted),
            ),
            const SizedBox(width: 4),
          ],
          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: isSelected ? ReclameJaColors.textDark : ReclameJaColors.surfaceDim,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '$count',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: isSelected ? ReclameJaColors.primaryYellow : ReclameJaColors.textDark,
              ),
            ),
          ),
        ],
      ),
      backgroundColor: ReclameJaColors.surfaceBright,
      selectedColor: ReclameJaColors.primaryYellow,
      checkmarkColor: Colors.transparent,
      showCheckmark: false,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: ReclameJaColors.borderSlate),
      ),
      onSelected: (val) {
        setState(() {
          _activeFilter = label;
        });
      },
    );
  }

  Widget _buildReportCard(Report report) {
    final textTheme = Theme.of(context).textTheme;
    final isResolved = report.status == 'Resolvido';
    final isInProgress = report.status == 'Em andamento';

    Color statusColor = ReclameJaColors.textMuted;
    Color statusBg = ReclameJaColors.surfaceLow;
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
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (context) => ReportDetailScreen(report: report)),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(14.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: isResolved
                          ? const Color(0xFFDCFCE7)
                          : isInProgress
                              ? const Color(0xFFFEF9C3)
                              : const Color(0xFFE0F2FE),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      report.category == 'Transporte'
                          ? Icons.directions_bus
                          : report.category == 'Saúde'
                              ? Icons.local_hospital
                              : Icons.construction,
                      color: isResolved
                          ? ReclameJaColors.secondaryEmerald
                          : isInProgress
                              ? Colors.amber.shade800
                              : ReclameJaColors.tertiaryBlue,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          report.title,
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            fontSize: 15,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            const Icon(Icons.location_on, size: 12, color: ReclameJaColors.textMuted),
                            const SizedBox(width: 4),
                            Expanded(
                              child: Text(
                                report.location,
                                style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusBg,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(color: statusColor, shape: BoxShape.circle),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          report.status,
                          style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const Divider(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.thumb_up_alt_outlined, size: 14, color: ReclameJaColors.secondaryEmerald),
                      const SizedBox(width: 4),
                      Text(
                        '${report.confirmationCount} pessoas apoiaram',
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: ReclameJaColors.secondaryEmerald,
                        ),
                      ),
                      if (report.comments.isNotEmpty) ...[
                        const SizedBox(width: 12),
                        const Icon(Icons.chat_bubble_outline, size: 13, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          '${report.comments.length}',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: ReclameJaColors.textMuted,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const Row(
                    children: [
                      Text(
                        'Ver detalhes',
                        style: TextStyle(
                          color: ReclameJaColors.secondaryEmerald,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Icon(Icons.arrow_forward, size: 14, color: ReclameJaColors.secondaryEmerald),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.location_city_outlined, size: 56, color: ReclameJaColors.surfaceDim),
            const SizedBox(height: 16),
            Text(
              'Nenhum chamado no momento',
              style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Não foram encontradas ocorrências abertas nesta categoria no seu raio de proximidade.',
              style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
