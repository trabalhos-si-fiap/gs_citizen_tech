import 'package:flutter/material.dart';
import '../../app_theme.dart';
import '../../services/report_store.dart';
import '../report_detail_screen.dart';
import '../welcome_screen.dart';

class ReportsTab extends StatefulWidget {
  final bool isVisitor;

  const ReportsTab({super.key, required this.isVisitor});

  @override
  State<ReportsTab> createState() => _ReportsTabState();
}

class _ReportsTabState extends State<ReportsTab> {
  String _activeSubFilter = 'Todos'; // 'Todos', 'Ativos', 'Concluídos'
  List<Report> _reports = [];

  @override
  void initState() {
    super.initState();
    _reports = ReportStore().allReports;
    _listenToStore();
  }

  void _listenToStore() {
    ReportStore().reportsStream.listen((list) {
      if (mounted) {
        setState(() {
          _reports = list;
        });
      }
    });
  }

  List<Report> _getFilteredReports() {
    List<Report> list = _reports;
    
    // For normal flow, we exclude reports created as "Anonymous" unless it is the current session
    // In this mock, we simply display all reports for demo fidelity.
    
    if (_activeSubFilter == 'Ativos') {
      return list.where((r) => r.status != 'Resolvido').toList();
    } else if (_activeSubFilter == 'Concluídos') {
      return list.where((r) => r.status == 'Resolvido').toList();
    }
    return list;
  }

  void _forceSyncDraft(Report draft) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Row(
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
            ),
            SizedBox(width: 10),
            Text('Sincronizando rascunho com o servidor municipal...'),
          ],
        ),
        backgroundColor: ReclameJaColors.secondaryEmerald,
      ),
    );

    Future.delayed(const Duration(milliseconds: 1500), () {
      if (mounted) {
        // Generate official protocol
        final officialId = '#CV-2026-${1000 + _reports.indexOf(draft)}';
        
        final syncedEvent = ReportEvent(
          title: 'Sincronizado',
          time: 'Hoje às 17:05',
          desc: 'Conexão restabelecida. Registro transmitido com sucesso à base de triagem central da Zeladoria.',
          actor: 'Sistema',
        );

        final updatedReport = draft.copyWith(
          id: officialId,
          isOffline: false,
          timeline: List.from(draft.timeline)..add(syncedEvent),
        );

        // Update the report in store
        final store = ReportStore();
        final idx = store.allReports.indexWhere((r) => r.id == draft.id);
        if (idx != -1) {
          // In our store, we can remove the old offline and add the new one or replace it
          // Let's replace it in memory
          store.allReports[idx] = updatedReport;
          // Trigger a change to stream to notify tabs
          store.toggleUserConfirmation(officialId); // small dummy update to trigger notify
        }

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Sincronizado! Protocolo provisório convertido para $officialId.'),
            backgroundColor: ReclameJaColors.secondaryEmerald,
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    if (widget.isVisitor) {
      return _buildVisitorView();
    }

    final filteredList = _getFilteredReports();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meus Reportes'),
        centerTitle: true,
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Sub-navigation Filter Bar
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Container(
              height: 48,
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceLow,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  _buildSubFilterTab('Todos'),
                  _buildSubFilterTab('Ativos'),
                  _buildSubFilterTab('Concluídos'),
                ],
              ),
            ),
          ),

          // Total counts summary
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Listando ${filteredList.length} ocorrências',
                  style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, fontWeight: FontWeight.bold),
                ),
                if (_reports.any((r) => r.isOffline))
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: ReclameJaColors.amberContainer,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'Pendente de rede',
                      style: textTheme.labelSmall?.copyWith(fontSize: 9, color: ReclameJaColors.onAmberContainer, fontWeight: FontWeight.bold),
                    ),
                  ),
              ],
            ),
          ),

          Expanded(
            child: filteredList.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    padding: const EdgeInsets.all(16.0),
                    itemCount: filteredList.length,
                    itemBuilder: (context, index) {
                      final r = filteredList[index];
                      return _buildReportRowItem(r);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildSubFilterTab(String label) {
    final isSelected = _activeSubFilter == label;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          setState(() {
            _activeSubFilter = label;
          });
        },
        child: Container(
          alignment: Alignment.center,
          margin: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: isSelected ? ReclameJaColors.surfaceBright : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              color: isSelected ? ReclameJaColors.textDark : ReclameJaColors.textMuted,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildReportRowItem(Report r) {
    final textTheme = Theme.of(context).textTheme;
    final isOffline = r.isOffline;
    final isResolved = r.status == 'Resolvido';
    final isInProgress = r.status == 'Em andamento';
    
    // Business Rule RT-39: Derive "Atrasado" state
    // Let's mock a report as overdue if it is an old ticket and not resolved
    final isOverdue = r.id.contains('5510') && !isResolved;

    Color statusColor = ReclameJaColors.textMuted;
    Color statusBg = ReclameJaColors.surfaceDim;
    if (isOffline) {
      statusColor = ReclameJaColors.onAmberContainer;
      statusBg = ReclameJaColors.amberContainer;
    } else if (isResolved) {
      statusColor = ReclameJaColors.onGreenContainer;
      statusBg = ReclameJaColors.greenContainer;
    } else if (isInProgress) {
      statusColor = ReclameJaColors.onAmberContainer;
      statusBg = ReclameJaColors.amberContainer;
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
            MaterialPageRoute(builder: (context) => ReportDetailScreen(report: r)),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Row 1: Protocol + Status badge
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Text(
                        r.id,
                        style: textTheme.labelMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: isOffline ? ReclameJaColors.textMuted : ReclameJaColors.secondaryEmerald,
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Overdue "Atrasado" Badge
                      if (isOverdue)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: ReclameJaColors.errorContainer,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'ATRASADO',
                            style: textTheme.labelSmall?.copyWith(fontSize: 8, color: ReclameJaColors.onErrorContainer, fontWeight: FontWeight.bold),
                          ),
                        ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusBg,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      isOffline ? 'Aguardando envio' : r.status,
                      style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),

              // Row 2: Title and details
              Text(
                r.title,
                style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold, fontSize: 15),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.location_on, size: 12, color: ReclameJaColors.textMuted),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      r.location,
                      style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const Divider(height: 20),

              // Row 3: Interactions and actions
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Criado em ${r.clientCreatedAt}',
                    style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted),
                  ),
                  if (isOffline)
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        backgroundColor: const Color(0xFFFEFDF0),
                        foregroundColor: ReclameJaColors.onAmberContainer,
                        minimumSize: Size.zero,
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                      ),
                      onPressed: () => _forceSyncDraft(r),
                      icon: const Icon(Icons.sync, size: 12),
                      label: const Text('Forçar Envio', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                    )
                  else
                    Row(
                      children: [
                        const Icon(Icons.chat_bubble_outline, size: 12, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          '${r.comments.length}',
                          style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(width: 12),
                        const Icon(Icons.thumb_up_alt_outlined, size: 12, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          '${r.confirmationCount}',
                          style: textTheme.bodySmall?.copyWith(color: ReclameJaColors.textMuted, fontWeight: FontWeight.bold),
                        ),
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
            const Icon(Icons.feed_outlined, size: 64, color: ReclameJaColors.surfaceDim),
            const SizedBox(height: 16),
            Text(
              'Nenhum chamado listado',
              style: textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Você ainda não registrou nenhum chamado sob esta classificação de filtro. Seus reportes de zeladoria aparecerão listados aqui.',
              style: textTheme.bodyMedium?.copyWith(color: ReclameJaColors.textMuted),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVisitorView() {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Meus Reportes'),
        centerTitle: true,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: const BoxDecoration(
                  color: ReclameJaColors.surfaceLow,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.lock_person_outlined, size: 64, color: ReclameJaColors.textMuted),
              ),
              const SizedBox(height: 24),
              Text(
                'Acompanhe seu histórico',
                style: textTheme.headlineMedium?.copyWith(fontSize: 22, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 10),
              Text(
                'Como visitante, você pode visualizar o mapa e o painel regional. Para registrar problemas e acompanhar o andamento de seus próprios chamados, faça login com segurança.',
                style: textTheme.bodyMedium?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: ReclameJaColors.primaryYellow,
                  foregroundColor: ReclameJaColors.textDark,
                  minimumSize: const Size.fromHeight(52),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: () {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(builder: (context) => const WelcomeScreen()),
                  );
                },
                child: const Text('Criar conta ou Fazer Login', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
