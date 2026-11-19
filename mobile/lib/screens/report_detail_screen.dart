import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';
import '../services/report_store.dart';
import '../services/api_client.dart';

class ReportDetailScreen extends StatefulWidget {
  final Report report;

  const ReportDetailScreen({super.key, required this.report});

  @override
  State<ReportDetailScreen> createState() => _ReportDetailScreenState();
}

class _ReportDetailScreenState extends State<ReportDetailScreen> {
  /// Intervalo do polling: o órgão muda status e prazo pelo painel web.
  static const refreshInterval = Duration(seconds: 20);

  late Report _report;
  bool _isMapVisible = false;

  ImageProvider? _resolveImageProvider(String? pathOrUrl) {
    if (pathOrUrl == null || pathOrUrl.isEmpty) return null;
    if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
      return NetworkImage(pathOrUrl);
    }
    return FileImage(File(pathOrUrl));
  }
  final _commentController = TextEditingController();
  StreamSubscription<List<Report>>? _storeSubscription;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _report = widget.report;
    _listenToStore();
    _refreshFromApi();
    _refreshTimer = Timer.periodic(
      refreshInterval,
      (_) => _refreshFromApi(silent: true),
    );
  }

  void _listenToStore() {
    // Keep internal screen state updated if the store changes (e.g. comments or confirmations)
    _storeSubscription = ReportStore().reportsStream.listen((list) {
      if (mounted) {
        final updated =
            list.firstWhere((r) => r.id == _report.id, orElse: () => _report);
        setState(() {
          _report = updated;
        });
      }
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _storeSubscription?.cancel();
    _commentController.dispose();
    super.dispose();
  }

  void _copyProtocolToClipboard() {
    Clipboard.setData(ClipboardData(text: _report.id));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle_outline, color: Colors.white),
            const SizedBox(width: 8),
            Text(
                'Protocolo ${_report.id} copiado para a área de transferência!'),
          ],
        ),
        backgroundColor: ReclameJaColors.secondaryEmerald,
      ),
    );
  }

  Future<void> _refreshFromApi({bool silent = false}) async {
    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) return;
    try {
      final detail = await ApiClient().getReport(apiId);
      ReportStore().upsertFromApi(detail);
      final response = await ApiClient().getComments(apiId);
      final items = (response['items'] as List? ?? const [])
          .whereType<Map>()
          .map(
            (comment) => {
              'author': 'Munícipe',
              'time': comment['created_at']?.toString() ?? '',
              'text': comment['content']?.toString() ?? '',
              'isOfficial': 'false',
            },
          )
          .toList();
      ReportStore().updateComments(apiId, items);
    } catch (_) {
      if (!mounted || silent) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Não foi possível atualizar o reporte agora.')),
      );
    }
  }

  Future<void> _toggleSupport() async {
    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) {
      _showFriendlyError('Essa confirmação estará disponível após o envio.');
      return;
    }
    try {
      final result = await ApiClient().confirmReport(apiId);
      final count = (result['confirmation_count'] as num).toInt();
      ReportStore().updateConfirmationCount(apiId, count);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
              'Obrigado por confirmar que essa situação também acontece por aí.'),
          backgroundColor: ReclameJaColors.secondaryEmerald,
        ),
      );
    } catch (error) {
      if (!mounted) return;
      _showFriendlyError(
        'Não foi possível registrar sua confirmação. Talvez você já tenha confirmado este reporte.',
      );
    }
  }

  Future<void> _addComment() async {
    final text = _commentController.text.trim();
    if (text.isEmpty) return;
    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) {
      _showFriendlyError('Você poderá comentar quando o reporte for enviado.');
      return;
    }
    try {
      await ApiClient().addComment(reportId: apiId, content: text);
      await _refreshFromApi();
    } catch (error) {
      if (!mounted) return;
      _showFriendlyError('Não foi possível enviar seu comentário agora.');
      return;
    }
    if (!mounted) return;
    _commentController.clear();
    FocusScope.of(context).unfocus();

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Nota comunitária adicionada com sucesso!'),
        backgroundColor: ReclameJaColors.secondaryEmerald,
      ),
    );
  }

  void _showFriendlyError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: ReclameJaColors.alertRed,
      ),
    );
  }

  Future<void> _reopenReport() async {
    if (_report.status != 'Resolvido') return;

    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) {
      _showFriendlyError('A reabertura estará disponível após o envio.');
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Reabrir Chamado',
            style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
        content: Text(
          'O problema na via ainda persiste após o recapeamento oficial? Se sim, você pode solicitar a reabertura do chamado técnico para nova vistoria.',
          style: GoogleFonts.hankenGrotesk(),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar',
                style: TextStyle(color: ReclameJaColors.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: ReclameJaColors.primaryYellow,
              foregroundColor: ReclameJaColors.textDark,
            ),
            onPressed: () async {
              Navigator.pop(context);
              try {
                final detail = await ApiClient().reopenReport(
                  reportId: apiId,
                  reason: 'O problema continua após o atendimento.',
                );
                ReportStore().upsertFromApi(detail);
                if (!mounted) return;
                messenger.showSnackBar(
                  const SnackBar(
                    content:
                        Text('Solicitamos uma nova análise para esse reporte.'),
                    backgroundColor: ReclameJaColors.secondaryEmerald,
                  ),
                );
              } catch (error) {
                if (!mounted) return;
                _showFriendlyError(
                  'Não foi possível reabrir. Verifique se o prazo para solicitar nova análise ainda está ativo.',
                );
              }
            },
            child: const Text('Reabrir chamado'),
          ),
        ],
      ),
    );
  }

  Future<void> _nudgeReport() async {
    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) {
      _showFriendlyError('Essa opção estará disponível após o envio.');
      return;
    }
    try {
      await ApiClient().nudgeReport(apiId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Seu pedido de atualização foi enviado.'),
          backgroundColor: ReclameJaColors.secondaryEmerald,
        ),
      );
    } catch (error) {
      if (!mounted) return;
      _showFriendlyError(
        'Não foi possível enviar o pedido agora. Ele pode não estar atrasado ou o limite de solicitações foi atingido.',
      );
    }
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
        title: const Text('Ocorrência'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_none),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                    content:
                        Text('Nenhuma notificação nova para este chamado.')),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Hero Photo Section with Badges overlay
            Container(
              height: 240,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                color: ReclameJaColors.surfaceLow,
                image: _resolveImageProvider(_report.imageUrl) != null
                    ? DecorationImage(
                        image: _resolveImageProvider(_report.imageUrl)!,
                        fit: BoxFit.cover,
                      )
                    : null,
              ),
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [
                      Colors.black.withValues(alpha: 0.6),
                      Colors.black.withValues(alpha: 0.1),
                    ],
                  ),
                ),
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Status Badge with Pulse Ring simulation
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: _report.status == 'Resolvido'
                                ? ReclameJaColors.greenContainer
                                : ReclameJaColors.primaryYellow,
                            borderRadius: BorderRadius.circular(999),
                            boxShadow: const [
                              BoxShadow(
                                  color: Colors.black26,
                                  blurRadius: 4,
                                  offset: Offset(0, 2)),
                            ],
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: _report.status == 'Resolvido'
                                      ? ReclameJaColors.secondaryEmerald
                                      : ReclameJaColors.textDark,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                _report.status.toUpperCase(),
                                style: textTheme.labelSmall?.copyWith(
                                  color: _report.status == 'Resolvido'
                                      ? ReclameJaColors.onGreenContainer
                                      : ReclameJaColors.textDark,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                        // Draft Indicator if offline
                        if (_report.isOffline)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: ReclameJaColors.alertRed,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              'Draft Local',
                              style: textTheme.labelSmall?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold),
                            ),
                          ),
                      ],
                    ),

                    // Bottom info block: category + photo count
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Flexible(
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.65),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.construction,
                                    color: ReclameJaColors.primaryYellow,
                                    size: 14),
                                const SizedBox(width: 6),
                                Flexible(
                                  child: Text(
                                    '${_report.category} • ${_report.subcategory}',
                                    style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _report.imageUrl != null ? '1 foto' : 'Sem foto',
                          style: const TextStyle(
                              color: Colors.white70, fontSize: 11),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Title and Location
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _report.title,
                  style: textTheme.displayMedium
                      ?.copyWith(fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.location_on,
                        color: ReclameJaColors.secondaryEmerald, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(_report.location,
                              style: textTheme.bodyLarge
                                  ?.copyWith(fontWeight: FontWeight.bold)),
                          Text(_report.details,
                              style: textTheme.bodySmall
                                  ?.copyWith(color: ReclameJaColors.textMuted)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                // Collapse toggle for mini-map
                GestureDetector(
                  onTap: () {
                    setState(() {
                      _isMapVisible = !_isMapVisible;
                    });
                  },
                  child: Padding(
                    padding: const EdgeInsets.only(left: 28.0),
                    child: Row(
                      children: [
                        const Icon(Icons.map,
                            size: 14, color: ReclameJaColors.tertiaryBlue),
                        const SizedBox(width: 4),
                        Text(
                          _isMapVisible
                              ? 'Esconder mapa detalhado'
                              : 'Ver mapa detalhado',
                          style: textTheme.labelMedium?.copyWith(
                              color: ReclameJaColors.tertiaryBlue,
                              fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
                if (_isMapVisible) ...[
                  const SizedBox(height: 12),
                  Container(
                    height: 140,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      color: ReclameJaColors.surfaceLow,
                      image: const DecorationImage(
                        image: NetworkImage(
                            'https://lh3.googleusercontent.com/aida-public/AB6AXuAteX67nFZrT7fEmVMHwiRPnpQlxUg1QjzJ4ZuW_EeivJSZmDQGw2_XCp3841SGDhksCrogHwdGhQt3wVBOaa5rhC7YMzqUOYYyp4IwBEdbMH2IxrMGhxCi-8sYCvuqlrUJaEtJvHrJIWpcTivi-1-7tpOIs7VbWAz31DZD9MkQKoqmuU8av2kKMP7oEEb10GvFz4l4prL77Ojjs6qCrPIB9ZTYwCH_TLVjJYRlPS_b'),
                        fit: BoxFit.cover,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 20),

            // Protocol clipboard copy box
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceLow,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Protocolo Oficial',
                            style: textTheme.labelSmall
                                ?.copyWith(color: ReclameJaColors.textMuted)),
                        const SizedBox(height: 2),
                        Text(
                          _report.id,
                          style: textTheme.headlineMedium?.copyWith(
                            fontSize: 15,
                            color: ReclameJaColors.secondaryEmerald,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 0.5,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      backgroundColor: ReclameJaColors.surfaceBright,
                      foregroundColor: ReclameJaColors.secondaryEmerald,
                      side:
                          const BorderSide(color: ReclameJaColors.borderSlate),
                      minimumSize: const Size(90, 40),
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8)),
                    ),
                    onPressed: _copyProtocolToClipboard,
                    icon: const Icon(Icons.content_copy, size: 14),
                    label: const Text('Copiar',
                        style: TextStyle(
                            fontSize: 12, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Official Response Forecast green box
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFDCFCE7),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF86EFAC)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: const BoxDecoration(
                      color: Color(0xFF16A34A),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.calendar_month,
                        color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _report.organ.isEmpty
                              ? 'Previsão Oficial • Reclame Já'
                              : 'Responsável: ${_report.organ}',
                          key: const ValueKey('report-detail-organ'),
                          style: textTheme.labelSmall?.copyWith(
                            color: const Color(0xFF14532D),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _report.forecast.isEmpty
                              ? 'Prazo definido quando o órgão receber'
                              : _report.forecast,
                          style: textTheme.bodyMedium?.copyWith(
                            color: const Color(0xFF14532D),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Stepped tracking path
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: ReclameJaColors.borderSlate),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Rastreamento do Chamado',
                          style: textTheme.titleMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFDCFCE7),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '${_report.timeline.length} etapas',
                          style: textTheme.labelSmall?.copyWith(
                              color: const Color(0xFF16A34A),
                              fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Vertical stepped path rendering dynamically from timeline list
                  ListView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _report.timeline.length +
                        (_report.status == 'Resolvido' ? 0 : 1),
                    itemBuilder: (context, index) {
                      final isTimelineEvent = index < _report.timeline.length;
                      final isLast = index ==
                          _report.timeline.length +
                              (_report.status == 'Resolvido' ? 0 : 1) -
                              1;

                      if (isTimelineEvent) {
                        final event = _report.timeline[index];
                        final isActiveStep =
                            index == _report.timeline.length - 1;

                        return IntrinsicHeight(
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Column(
                                children: [
                                  Container(
                                    width: 24,
                                    height: 24,
                                    decoration: BoxDecoration(
                                      color: isActiveStep
                                          ? ReclameJaColors.primaryYellow
                                          : const Color(0xFF16A34A),
                                      shape: BoxShape.circle,
                                      border: Border.all(
                                        color: isActiveStep
                                            ? Colors.orange
                                            : const Color(0xFF86EFAC),
                                        width: isActiveStep ? 2 : 1,
                                      ),
                                    ),
                                    child: Icon(
                                      isActiveStep
                                          ? Icons.trending_up
                                          : Icons.check,
                                      size: 14,
                                      color: isActiveStep
                                          ? ReclameJaColors.textDark
                                          : Colors.white,
                                    ),
                                  ),
                                  if (!isLast)
                                    Expanded(
                                      child: Container(
                                        width: 2,
                                        color: const Color(0xFF16A34A),
                                      ),
                                    ),
                                ],
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.only(bottom: 20.0),
                                  child: isActiveStep
                                      ? Container(
                                          padding: const EdgeInsets.all(12),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFFFEFDF0),
                                            borderRadius:
                                                BorderRadius.circular(10),
                                            border: Border.all(
                                                color: ReclameJaColors
                                                    .primaryYellow),
                                          ),
                                          child: Column(
                                            crossAxisAlignment:
                                                CrossAxisAlignment.start,
                                            children: [
                                              Row(
                                                mainAxisAlignment:
                                                    MainAxisAlignment
                                                        .spaceBetween,
                                                children: [
                                                  Expanded(
                                                    child: Text(
                                                      '${index + 1}. ${event.title}',
                                                      style: const TextStyle(
                                                          fontWeight:
                                                              FontWeight.bold,
                                                          fontSize: 13,
                                                          color:
                                                              Color(0xFF451A03)),
                                                      maxLines: 1,
                                                      overflow: TextOverflow.ellipsis,
                                                    ),
                                                  ),
                                                  const SizedBox(width: 8),
                                                  Text(event.time,
                                                      style: const TextStyle(
                                                          fontSize: 10,
                                                          color: Color(
                                                              0xFF78350F))),
                                                ],
                                              ),
                                              const SizedBox(height: 4),
                                              Text(event.desc,
                                                  style: const TextStyle(
                                                      fontSize: 12,
                                                      color: Color(0xFF78350F),
                                                      height: 1.3)),
                                              const SizedBox(height: 6),
                                              Row(
                                                children: [
                                                  const Icon(Icons.badge,
                                                      size: 12,
                                                      color: Color(0xFF9A3412)),
                                                  const SizedBox(width: 4),
                                                  Text(
                                                      'Responsável: ${event.actor}',
                                                      style: const TextStyle(
                                                          fontSize: 10,
                                                          fontWeight:
                                                              FontWeight.bold,
                                                          color: Color(
                                                              0xFF9A3412))),
                                                ],
                                              ),
                                            ],
                                          ),
                                        )
                                      : Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Expanded(
                                                  child: Text(
                                                      '${index + 1}. ${event.title}',
                                                      style: const TextStyle(
                                                          fontWeight:
                                                              FontWeight.bold,
                                                          fontSize: 13),
                                                      maxLines: 1,
                                                      overflow: TextOverflow.ellipsis),
                                                ),
                                                const SizedBox(width: 8),
                                                Text(event.time,
                                                    style: textTheme.bodySmall
                                                        ?.copyWith(
                                                            color:
                                                                ReclameJaColors
                                                                    .textMuted)),
                                              ],
                                            ),
                                            const SizedBox(height: 2),
                                            Text(event.desc,
                                                style: textTheme.bodySmall
                                                    ?.copyWith(
                                                        color: ReclameJaColors
                                                            .textMuted,
                                                        height: 1.3)),
                                          ],
                                        ),
                                ),
                              ),
                            ],
                          ),
                        );
                      } else {
                        // Pending Next Stage
                        return IntrinsicHeight(
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Column(
                                children: [
                                  Container(
                                    width: 24,
                                    height: 24,
                                    decoration: const BoxDecoration(
                                      color: ReclameJaColors.surfaceLow,
                                      shape: BoxShape.circle,
                                    ),
                                    child: const Icon(Icons.hourglass_empty,
                                        size: 12,
                                        color: ReclameJaColors.textMuted),
                                  ),
                                ],
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.only(top: 4.0),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${_report.timeline.length + 1}. Resolvido',
                                        style: textTheme.labelLarge?.copyWith(
                                            color: ReclameJaColors.textMuted),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        'Recapeamento definitivo e envio de foto oficial de homologação.',
                                        style: textTheme.bodySmall?.copyWith(
                                            color: ReclameJaColors.textMuted),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        );
                      }
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Neighborhood Engagement support block
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceLow,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Flexible(
                        child: Text(
                          'Voz da Vizinhança',
                          style: textTheme.titleMedium,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Mock avatar stack (overlapping avatars)
                      const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          SizedBox(
                            width: 60,
                            height: 24,
                            child: Stack(
                              children: [
                                Positioned(
                                    left: 0,
                                    child: CircleAvatar(
                                        radius: 12,
                                        backgroundColor: Colors.blue,
                                        child: Text('JS',
                                            style: TextStyle(
                                                fontSize: 8,
                                                color: Colors.white,
                                                fontWeight: FontWeight.bold)))),
                                Positioned(
                                    left: 18,
                                    child: CircleAvatar(
                                        radius: 12,
                                        backgroundColor: Colors.green,
                                        child: Text('MC',
                                            style: TextStyle(
                                                fontSize: 8,
                                                color: Colors.white,
                                                fontWeight: FontWeight.bold)))),
                                Positioned(
                                    left: 36,
                                    child: CircleAvatar(
                                        radius: 12,
                                        backgroundColor: Colors.amber,
                                        child: Text('RL',
                                            style: TextStyle(
                                                fontSize: 8,
                                                color: Colors.white,
                                                fontWeight: FontWeight.bold)))),
                              ],
                            ),
                          ),
                          SizedBox(width: 4),
                          Text('+12',
                              style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: ReclameJaColors.textMuted)),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    textBaseline: TextBaseline.alphabetic,
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    children: [
                      Text(
                        '${_report.confirmationCount}',
                        style: textTheme.displayMedium?.copyWith(
                          fontSize: 32,
                          color: ReclameJaColors.secondaryEmerald,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'moradores confirmaram este problema',
                          style: textTheme.bodyMedium
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Cada confirmação valida o impacto e eleva o nível de prioridade no despacho das frentes de trabalho municipais.',
                    style: textTheme.bodySmall?.copyWith(
                        color: ReclameJaColors.textMuted, height: 1.3),
                  ),
                  const SizedBox(height: 12),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _report.isUserConfirmed
                          ? ReclameJaColors.secondaryEmerald
                          : ReclameJaColors.primaryYellow,
                      foregroundColor: _report.isUserConfirmed
                          ? Colors.white
                          : ReclameJaColors.textDark,
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    onPressed: _toggleSupport,
                    icon: Icon(
                        _report.isUserConfirmed ? Icons.check : Icons.thumb_up),
                    label: Text(
                      _report.isUserConfirmed
                          ? 'Você confirmou este problema'
                          : 'Eu também vi isso (+1)',
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Comments and updates section
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: ReclameJaColors.surfaceBright,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: ReclameJaColors.borderSlate),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Comentários e atualizações',
                          style: textTheme.titleMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFDCFCE7),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '${_report.comments.length}',
                          style: textTheme.labelSmall?.copyWith(
                              color: const Color(0xFF16A34A),
                              fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Comments List
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _report.comments.length,
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final c = _report.comments[index];
                      final isOfficial = c['isOfficial'] == 'true';

                      return Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: isOfficial
                              ? const Color(0xFFF0FDF4)
                              : ReclameJaColors.surfaceLow,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isOfficial
                                ? const Color(0xFF86EFAC)
                                : Colors.transparent,
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      c['author']!,
                                      style: TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                        color: isOfficial
                                            ? const Color(0xFF15803D)
                                            : ReclameJaColors.textDark,
                                      ),
                                    ),
                                    if (isOfficial) ...[
                                      const SizedBox(width: 4),
                                      const Icon(Icons.verified,
                                          color: Color(0xFF16A34A), size: 14),
                                    ],
                                  ],
                                ),
                                Text(
                                  c['time']!,
                                  style: const TextStyle(
                                      fontSize: 10,
                                      color: ReclameJaColors.textMuted),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              c['text']!,
                              style: const TextStyle(fontSize: 12, height: 1.3),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 16),

                  // Add note trigger
                  Text('Adicionar nota comunitária ou detalhe',
                      style: textTheme.labelMedium
                          ?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _commentController,
                          decoration: const InputDecoration(
                            hintText:
                                "Ex.: 'A água da chuva cobriu o buraco'...",
                            contentPadding: EdgeInsets.symmetric(
                                horizontal: 12, vertical: 10),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Camera complement
                      IconButton(
                        icon: const Icon(Icons.add_a_photo,
                            color: ReclameJaColors.textMuted),
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content:
                                    Text('Selecione uma imagem complementar.')),
                          );
                        },
                      ),
                      IconButton(
                        icon: const Icon(Icons.send,
                            color: ReclameJaColors.secondaryEmerald),
                        onPressed: _addComment,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Share & Reopen Button Controls
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: ReclameJaColors.primaryYellow,
                    foregroundColor: ReclameJaColors.textDark,
                    minimumSize: const Size.fromHeight(52),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                            'Link do chamado ${_report.id} copiado para compartilhamento!'),
                        backgroundColor: ReclameJaColors.secondaryEmerald,
                      ),
                    );
                  },
                  icon: const Icon(Icons.share, size: 18),
                  label: const Text('Compartilhar com vizinhos',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 10),

                // Reopen / Cobrar Novamente conditional controls
                if (_report.status == 'Resolvido') ...[
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: ReclameJaColors.secondaryEmerald,
                      side: const BorderSide(
                          color: ReclameJaColors.secondaryEmerald),
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: _reopenReport,
                    icon: const Icon(Icons.replay),
                    label: const Text('Reabrir chamado',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Ação disponível caso o problema persista após a conclusão oficial.',
                    style: TextStyle(
                        fontSize: 10, color: ReclameJaColors.textMuted),
                    textAlign: TextAlign.center,
                  ),
                ] else ...[
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: ReclameJaColors.textDark,
                      side:
                          const BorderSide(color: ReclameJaColors.borderSlate),
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: _nudgeReport,
                    icon: const Icon(Icons.campaign),
                    label: const Text('Cobrar novamente',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Envia uma nova notificação de cobrança direta para agilizar a vistoria do órgão.',
                    style: TextStyle(
                        fontSize: 10, color: ReclameJaColors.textMuted),
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: 16),

                // Support links
                Wrap(
                  alignment: WrapAlignment.center,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 4,
                  children: [
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        foregroundColor: ReclameJaColors.textMuted,
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content:
                                  Text('Encaminhando à Ouvidoria Geral...')),
                        );
                      },
                      icon:
                          const Icon(Icons.contact_support_outlined, size: 14),
                      label: const Text('Falar com Ouvidoria',
                          style: TextStyle(
                              fontSize: 11,
                              decoration: TextDecoration.underline)),
                    ),
                    const Text('•',
                        style: TextStyle(color: ReclameJaColors.surfaceDim)),
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        foregroundColor: ReclameJaColors.alertRed,
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text(
                                  'Abuso reportado para auditoria da equipe do Voz Cidadã.')),
                        );
                      },
                      icon: const Icon(Icons.flag_outlined, size: 14),
                      label: const Text('Relatar inconsistência',
                          style: TextStyle(
                              fontSize: 11,
                              decoration: TextDecoration.underline)),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
