import 'dart:async';

import 'package:flutter/material.dart';
import '../../app_theme.dart';
import '../../services/api_client.dart';
import '../../services/outbox_store.dart';
import '../../services/push_service.dart';
import '../../services/report_store.dart';
import '../../services/session_store.dart';
import '../report_detail_screen.dart';
import '../welcome_screen.dart';

class ReportsTab extends StatefulWidget {
  final bool isVisitor;

  const ReportsTab({super.key, required this.isVisitor});

  @override
  State<ReportsTab> createState() => _ReportsTabState();
}

class _ReportsTabState extends State<ReportsTab> with WidgetsBindingObserver {
  String _activeSubFilter = 'Todos'; // 'Todos', 'Ativos', 'Concluídos'
  List<Report> _reports = [];
  StreamSubscription<List<Report>>? _storeSubscription;
  StreamSubscription<String?>? _pushSubscription;
  Timer? _pollTimer;
  String? _loadError;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _reports = ReportStore().allReports;
    _listenToStore();
    _pushSubscription = PushService.reportUpdates.listen(_refreshPushedReport);
    _refreshFromApi();
    _pollTimer = Timer.periodic(
      const Duration(seconds: 60),
      (_) => _refreshFromApi(),
    );
  }

  void _listenToStore() {
    _storeSubscription = ReportStore().reportsStream.listen((list) {
      if (mounted) {
        setState(() {
          _reports = list;
        });
      }
    });
  }

  Future<void> _refreshPushedReport(String? reportId) async {
    if (reportId == null || reportId.isEmpty) {
      await _refreshFromApi();
      return;
    }
    try {
      final detail = await ApiClient().getReport(reportId);
      ReportStore().upsertFromApi(detail);
    } catch (error) {
      if (mounted) setState(() => _loadError = error.toString());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshFromApi();
      unawaited(_syncPushRegistration());
    }
  }

  Future<void> _syncPushRegistration() async {
    try {
      await PushService.initializeAfterLogin();
    } catch (error) {
      if (mounted) setState(() => _loadError = error.toString());
    }
  }

  Future<void> _refreshFromApi() async {
    if (widget.isVisitor || SessionStore.accessToken == null || _isLoading) {
      return;
    }
    _isLoading = true;
    try {
      final before = await OutboxStore.load();
      Object? outboxError;
      try {
        final result = await ApiClient().flushOutbox();
        outboxError = result.error;
      } catch (error) {
        outboxError = error;
      }
      final after = await OutboxStore.load();
      final pendingIds = after.map((item) => item['id'] as String).toSet();
      for (final item in before) {
        final id = item['id'] as String;
        if (!pendingIds.contains(id)) {
          ReportStore().removeByApiId(id);
        }
      }
      final page = await ApiClient().listMyReports();
      final items = (page['items'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();
      ReportStore().replaceFromApi(items);
      if (mounted) setState(() => _loadError = outboxError?.toString());
    } catch (error) {
      if (mounted) setState(() => _loadError = error.toString());
    } finally {
      _isLoading = false;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pollTimer?.cancel();
    _storeSubscription?.cancel();
    _pushSubscription?.cancel();
    super.dispose();
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

  Future<void> _forceSyncDraft(Report draft) async {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Row(
          children: [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: Colors.white),
            ),
            SizedBox(width: 10),
            Text('Sincronizando rascunho com o servidor municipal...'),
          ],
        ),
        backgroundColor: ReclameJaColors.secondaryEmerald,
      ),
    );
    final result = await ApiClient().flushOutbox();
    if (!mounted) return;
    await _refreshFromApi();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          result.synced > 0 && !result.hasPendingFailure
              ? 'Reporte enviado. O protocolo foi atualizado.'
              : result.synced > 0
                  ? 'Alguns reportes foram enviados; outro ainda precisa de atenção.'
                  : 'Ainda não foi possível enviar. Vamos tentar novamente quando houver conexão.',
        ),
        backgroundColor: result.synced > 0
            ? ReclameJaColors.secondaryEmerald
            : ReclameJaColors.onAmberContainer,
      ),
    );
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
            padding:
                const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
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
          if (_loadError != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Text(
                'Não foi possível atualizar seus reportes. Verifique a conexão e tente novamente.',
                style: textTheme.bodySmall
                    ?.copyWith(color: ReclameJaColors.alertRed),
              ),
            ),
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Listando ${filteredList.length} ocorrências',
                  style: textTheme.bodySmall?.copyWith(
                      color: ReclameJaColors.textMuted,
                      fontWeight: FontWeight.bold),
                ),
                if (_reports.any((r) => r.isOffline))
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: ReclameJaColors.amberContainer,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'Pendente de rede',
                      style: textTheme.labelSmall?.copyWith(
                          fontSize: 9,
                          color: ReclameJaColors.onAmberContainer,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
              ],
            ),
          ),

          Expanded(
            child: filteredList.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    // Folga no fim para o último cartão sair de baixo do botão
                    // flutuante "Reportar problema" do HomeShell.
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
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
            color:
                isSelected ? ReclameJaColors.surfaceBright : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              color: isSelected
                  ? ReclameJaColors.textDark
                  : ReclameJaColors.textMuted,
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
            MaterialPageRoute(
                builder: (context) => ReportDetailScreen(report: r)),
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
                  Expanded(
                    child: Row(
                      children: [
                        Flexible(
                          child: Text(
                            r.id,
                            style: textTheme.labelMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: isOffline
                                  ? ReclameJaColors.textMuted
                                  : ReclameJaColors.secondaryEmerald,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (isOverdue) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: ReclameJaColors.errorContainer,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              'ATRASADO',
                              style: textTheme.labelSmall?.copyWith(
                                  fontSize: 8,
                                  color: ReclameJaColors.onErrorContainer,
                                  fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusBg,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      isOffline ? 'Aguardando envio' : r.status,
                      style: TextStyle(
                          color: statusColor,
                          fontSize: 10,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),

              // Row 2: Title and details
              Text(
                r.title,
                style: textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.bold, fontSize: 15),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              if (r.classificationLabel.isNotEmpty) ...[
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(Icons.category_outlined,
                        size: 12, color: ReclameJaColors.textMuted),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        r.classificationLabel,
                        style: textTheme.bodySmall?.copyWith(
                            color: ReclameJaColors.textDark,
                            fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.location_on,
                      size: 12, color: ReclameJaColors.textMuted),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      r.location,
                      style: textTheme.bodySmall
                          ?.copyWith(color: ReclameJaColors.textMuted),
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
                    style: textTheme.bodySmall
                        ?.copyWith(color: ReclameJaColors.textMuted),
                  ),
                  if (isOffline)
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        backgroundColor: const Color(0xFFFEFDF0),
                        foregroundColor: ReclameJaColors.onAmberContainer,
                        minimumSize: Size.zero,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(6)),
                      ),
                      onPressed: () => _forceSyncDraft(r),
                      icon: const Icon(Icons.sync, size: 12),
                      label: const Text('Forçar Envio',
                          style: TextStyle(
                              fontSize: 10, fontWeight: FontWeight.bold)),
                    )
                  else
                    Row(
                      children: [
                        const Icon(Icons.chat_bubble_outline,
                            size: 12, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          '${r.comments.length}',
                          style: textTheme.bodySmall?.copyWith(
                              color: ReclameJaColors.textMuted,
                              fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(width: 12),
                        const Icon(Icons.thumb_up_alt_outlined,
                            size: 12, color: ReclameJaColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          '${r.confirmationCount}',
                          style: textTheme.bodySmall?.copyWith(
                              color: ReclameJaColors.textMuted,
                              fontWeight: FontWeight.bold),
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
            const Icon(Icons.feed_outlined,
                size: 64, color: ReclameJaColors.surfaceDim),
            const SizedBox(height: 16),
            Text(
              'Nenhum chamado listado',
              style:
                  textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Você ainda não registrou nenhum chamado sob esta classificação de filtro. Seus reportes de zeladoria aparecerão listados aqui.',
              style: textTheme.bodyMedium
                  ?.copyWith(color: ReclameJaColors.textMuted),
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
                child: const Icon(Icons.lock_person_outlined,
                    size: 64, color: ReclameJaColors.textMuted),
              ),
              const SizedBox(height: 24),
              Text(
                'Acompanhe seu histórico',
                style: textTheme.headlineMedium
                    ?.copyWith(fontSize: 22, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 10),
              Text(
                'Como visitante, você pode visualizar o mapa e o painel regional. Para registrar problemas e acompanhar o andamento de seus próprios chamados, faça login com segurança.',
                style: textTheme.bodyMedium
                    ?.copyWith(color: ReclameJaColors.textMuted, height: 1.4),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: ReclameJaColors.primaryYellow,
                  foregroundColor: ReclameJaColors.textDark,
                  minimumSize: const Size.fromHeight(52),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: () {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(
                        builder: (context) => const WelcomeScreen()),
                  );
                },
                child: const Text('Criar conta ou Fazer Login',
                    style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
