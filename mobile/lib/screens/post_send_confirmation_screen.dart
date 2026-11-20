import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../app_theme.dart';
import '../services/report_store.dart';
import '../services/api_client.dart';
import '../services/category_labels.dart';
import 'report_detail_screen.dart';

class PostSendConfirmationScreen extends StatefulWidget {
  final Report report;

  const PostSendConfirmationScreen({super.key, required this.report});

  @override
  State<PostSendConfirmationScreen> createState() =>
      _PostSendConfirmationScreenState();
}

class _WorkflowStep {
  const _WorkflowStep({
    required this.icon,
    required this.title,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String description;
}

class _PostSendConfirmationScreenState
    extends State<PostSendConfirmationScreen> {
  /// Intervalo entre consultas enquanto a IA classifica.
  static const pollInterval = Duration(seconds: 3);

  late Report _report = widget.report;
  bool _isConfirmedByMunicipe = false;
  Timer? _pollTimer;

  /// Enviado e ainda sem classificação: consulta a API até a IA responder.
  bool get _isAnalysing =>
      _report.apiId != null &&
      !_report.isOffline &&
      (_report.triageState.isEmpty ||
          _report.triageState == 'pending_classification');

  bool get _isClassificationConfirmed =>
      _isConfirmedByMunicipe ||
      _report.triageState == 'confirmed' ||
      _report.triageState == 'auto_confirmed';

  ImageProvider? _resolveImageProvider(String? pathOrUrl) {
    if (pathOrUrl == null || pathOrUrl.isEmpty) return null;
    if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
      return NetworkImage(pathOrUrl);
    }
    return FileImage(File(pathOrUrl));
  }

  @override
  void initState() {
    super.initState();
    if (_isAnalysing) _refreshClassification();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _refreshClassification() async {
    try {
      _showReport(await ApiClient().getReport(_report.apiId!));
    } catch (_) {
      // Sem resposta agora: tenta de novo no próximo ciclo.
    }
    if (mounted && _isAnalysing) {
      _pollTimer = Timer(pollInterval, _refreshClassification);
    }
  }

  /// Atualiza o store e a tela com o reporte devolvido pela API.
  void _showReport(Map<String, dynamic> detail) {
    final updated = ReportStore().upsertFromApi(detail);
    if (!mounted) return;
    setState(() {
      // A foto local continua na tela enquanto a da API não fica pronta.
      _report =
          updated.copyWith(imageUrl: updated.imageUrl ?? _report.imageUrl);
    });
  }

  Future<void> _confirmData() async {
    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) {
      _showMessage('A confirmação ficará disponível após o envio do reporte.');
      return;
    }
    try {
      _showReport(await ApiClient().triageReport(
        reportId: apiId,
        action: 'confirm',
      ));
      if (!mounted) return;
      setState(() => _isConfirmedByMunicipe = true);
      _showMessage('Classificação confirmada e encaminhada.', success: true);
    } catch (error) {
      if (!mounted) return;
      _showMessage(
        'Ainda estamos preparando a classificação. Tente novamente em instantes.',
      );
    }
  }

  Future<void> _correctData() async {
    final apiId = _report.apiId;
    if (apiId == null || _report.isOffline) {
      _showMessage('A correção ficará disponível após o envio.');
      return;
    }
    final choice = await showDialog<({String category, String subcategory})>(
      context: context,
      builder: (context) => const _CorrectClassificationDialog(),
    );
    if (choice == null || !mounted) return;
    try {
      _showReport(await ApiClient().triageReport(
        reportId: apiId,
        action: 'correct',
        category: choice.category,
        subcategory: choice.subcategory,
      ));
      if (!mounted) return;
      setState(() => _isConfirmedByMunicipe = true);
      _showMessage('Classificação atualizada.', success: true);
    } catch (error) {
      if (!mounted) return;
      _showMessage(
        'Não foi possível atualizar agora. Tente novamente em instantes.',
      );
    }
  }

  void _showMessage(String message, {bool success = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: success
            ? ReclameJaColors.secondaryEmerald
            : ReclameJaColors.alertRed,
      ),
    );
  }

  List<_WorkflowStep> _workflowSteps() {
    final category = _report.category.toLowerCase();
    if (category.contains('transporte') || category.contains('mobilidade')) {
      return const [
        _WorkflowStep(
          icon: Icons.directions_bus_outlined,
          title: '1. Encaminhamento à mobilidade',
          description:
              'O relato é enviado à central responsável pela operação de transporte.',
        ),
        _WorkflowStep(
          icon: Icons.manage_search_outlined,
          title: '2. Análise da operação',
          description:
              'A operação avalia a linha, parada ou trajeto informado e define a ação necessária.',
        ),
        _WorkflowStep(
          icon: Icons.notifications_active_outlined,
          title: '3. Atualização do atendimento',
          description:
              'Você receberá as atualizações e a resposta da operação pelo aplicativo.',
        ),
      ];
    }
    if (category.contains('saúde') || category.contains('saude')) {
      return const [
        _WorkflowStep(
          icon: Icons.health_and_safety_outlined,
          title: '1. Encaminhamento à ouvidoria',
          description:
              'A manifestação é encaminhada à ouvidoria responsável pelo atendimento de saúde.',
        ),
        _WorkflowStep(
          icon: Icons.fact_check_outlined,
          title: '2. Análise do atendimento',
          description:
              'A unidade responsável analisa as informações relatadas e o histórico do atendimento.',
        ),
        _WorkflowStep(
          icon: Icons.notifications_active_outlined,
          title: '3. Retorno ao cidadão',
          description:
              'A resposta da ouvidoria e eventuais atualizações serão enviadas pelo aplicativo.',
        ),
      ];
    }
    return const [
      _WorkflowStep(
        icon: Icons.assignment_turned_in_outlined,
        title: '1. Encaminhamento oficial',
        description:
            'Inclusão no sistema de zeladoria e encaminhamento à base técnica responsável.',
      ),
      _WorkflowStep(
        icon: Icons.engineering_outlined,
        title: '2. Vistoria técnica',
        description:
            'A equipe de campo avalia a extensão do problema e define a ordem de serviço.',
      ),
      _WorkflowStep(
        icon: Icons.notifications_active_outlined,
        title: '3. Notificações diretas',
        description:
            'Você receberá as atualizações de vistoria, execução e conclusão do reparo.',
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final workflowSteps = _workflowSteps();

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
                        child: const Icon(Icons.task_alt,
                            color: Color(0xFF16A34A), size: 34),
                      ),
                      Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          color: const Color(0xFF16A34A),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                        child: const Icon(Icons.check,
                            color: Colors.white, size: 14),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Protocol Badge
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFFDCFCE7),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: const Color(0xFF86EFAC)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.tag,
                            size: 14, color: Color(0xFF14532D)),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            'Protocolo ${_report.id}',
                            style: textTheme.labelSmall?.copyWith(
                              color: const Color(0xFF14532D),
                              fontWeight: FontWeight.bold,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Entendemos o seu reporte',
                    style: textTheme.displayMedium
                        ?.copyWith(fontSize: 26, fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _report.isOffline
                        ? 'Seu reporte está salvo no aparelho e será enviado quando a conexão voltar.'
                        : _isAnalysing
                            ? 'A IA está classificando o seu relato. Isso costuma levar alguns segundos.'
                            : 'Revise a categoria e confirme o reporte para encaminhamento.',
                    style: textTheme.bodyMedium
                        ?.copyWith(color: ReclameJaColors.textMuted),
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
                      image: _resolveImageProvider(_report.imageUrl) != null
                          ? DecorationImage(
                              image: _resolveImageProvider(_report.imageUrl)!,
                              fit: BoxFit.cover,
                            )
                          : null,
                    ),
                    child: Stack(
                      children: [
                        if (_report.imageUrl == null)
                          const Center(
                            child: Icon(Icons.photo,
                                size: 48, color: ReclameJaColors.textMuted),
                          ),
                        Positioned(
                          top: 10,
                          right: 10,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.95),
                              borderRadius: BorderRadius.circular(999),
                              border:
                                  Border.all(color: const Color(0xFF86EFAC)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.verified,
                                    color: Color(0xFF16A34A), size: 14),
                                const SizedBox(width: 4),
                                Text(
                                  _statusBadge,
                                  style: const TextStyle(
                                      color: Color(0xFF16A34A),
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                          ),
                        ),
                        Positioned(
                          bottom: 10,
                          left: 10,
                          right: 10,
                          child: Align(
                            alignment: Alignment.centerLeft,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.7),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.location_on,
                                      color: Colors.white, size: 14),
                                  const SizedBox(width: 4),
                                  Flexible(
                                    child: Text(
                                      _report.location,
                                      style: const TextStyle(
                                          color: Colors.white, fontSize: 11),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
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
                      const Icon(Icons.auto_fix_high,
                          size: 16, color: ReclameJaColors.secondaryEmerald),
                      const SizedBox(width: 6),
                      Text('Classificação da IA',
                          style: textTheme.labelSmall
                              ?.copyWith(color: ReclameJaColors.textMuted)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: ReclameJaColors.surfaceLow,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                          color: ReclameJaColors.surfaceDim
                              .withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: const BoxDecoration(
                            color: Color(0xFFDCFCE7),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.construction,
                              color: Color(0xFF16A34A), size: 20),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (_isAnalysing)
                                Row(
                                  children: [
                                    const SizedBox(
                                      width: 14,
                                      height: 14,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        'Analisando o seu relato…',
                                        style: textTheme.labelLarge?.copyWith(
                                            fontWeight: FontWeight.bold),
                                      ),
                                    ),
                                  ],
                                )
                              else
                                Text(
                                  _report.isOffline
                                      ? 'A classificação acontece depois do envio.'
                                      : _report.classificationLabel,
                                  style: textTheme.labelLarge
                                      ?.copyWith(fontWeight: FontWeight.bold),
                                ),
                              const SizedBox(height: 2),
                              Text(
                                _isAnalysing
                                    ? 'A categoria sugerida aparece aqui em instantes.'
                                    : 'A classificação poderá ser revisada pela equipe responsável.',
                                style: textTheme.bodySmall?.copyWith(
                                    color: ReclameJaColors.textMuted),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Urgência estimada pela IA
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Urgência',
                          style: textTheme.labelSmall
                              ?.copyWith(color: ReclameJaColors.textMuted)),
                      Text(
                        _isAnalysing || _report.isOffline
                            ? 'Em análise'
                            : labelForUrgency(_report.urgency),
                        style: textTheme.labelSmall
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      for (var level = 1; level <= 3; level++) ...[
                        if (level > 1) const SizedBox(width: 6),
                        Expanded(
                          child: Container(
                            height: 6,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(999),
                              color: level <= _urgencyLevel
                                  ? Colors.amber.shade500
                                  : ReclameJaColors.surfaceDim,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Destination Department Card
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF0FDF4),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                          color:
                              const Color(0xFF86EFAC).withValues(alpha: 0.8)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.account_balance,
                            color: Color(0xFF16A34A), size: 22),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Destino do Chamado',
                                style: textTheme.labelSmall?.copyWith(
                                    color: const Color(0xFF15803D),
                                    fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                _report.organ.isNotEmpty
                                    ? _report.organ
                                    : 'Definido após a confirmação da classificação.',
                                style: textTheme.labelLarge?.copyWith(
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                    height: 1.3),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Validation Action Blocks
                  if (_report.triageState == 'awaiting_user' ||
                      _isClassificationConfirmed)
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (!_isClassificationConfirmed) ...[
                          Center(
                            child: Text(
                              'As informações correspondem ao problema?',
                              style: textTheme.bodyMedium,
                            ),
                          ),
                          const SizedBox(height: 12),
                        ],
                        if (!_isClassificationConfirmed)
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton.icon(
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: ReclameJaColors.textDark,
                                    side: const BorderSide(
                                        color: ReclameJaColors.borderSlate),
                                    minimumSize: const Size.fromHeight(48),
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(10)),
                                  ),
                                  onPressed: _correctData,
                                  icon: const Icon(Icons.edit, size: 16),
                                  label: const Text('Corrigir dados',
                                      style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.bold)),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: ElevatedButton.icon(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor:
                                        ReclameJaColors.primaryYellow,
                                    foregroundColor: ReclameJaColors.textDark,
                                    minimumSize: const Size.fromHeight(48),
                                    shape: RoundedRectangleBorder(
                                        borderRadius:
                                            BorderRadius.circular(10)),
                                  ),
                                  onPressed: _confirmData,
                                  icon: const Icon(Icons.thumb_up_alt_outlined,
                                      size: 16),
                                  label: const Text('Sim, confirmar',
                                      style: TextStyle(
                                          fontSize: 13,
                                          fontWeight: FontWeight.bold)),
                                ),
                              ),
                            ],
                          )
                        else
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 16, vertical: 12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFDCFCE7),
                              borderRadius: BorderRadius.circular(12),
                              border:
                                  Border.all(color: const Color(0xFF86EFAC)),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.check_circle,
                                    color: Color(0xFF16A34A), size: 20),
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
                      Text('O que vai acontecer agora',
                          style: textTheme.titleMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFDCFCE7),
                          borderRadius: BorderRadius.circular(99),
                        ),
                        child: Row(
                          children: [
                            Container(
                                width: 5,
                                height: 5,
                                decoration: const BoxDecoration(
                                    color: Color(0xFF16A34A),
                                    shape: BoxShape.circle)),
                            const SizedBox(width: 4),
                            Text(
                              'Em fluxo',
                              style: textTheme.labelSmall?.copyWith(
                                  color: const Color(0xFF16A34A),
                                  fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  ...workflowSteps.asMap().entries.map(
                        (entry) => _buildTimelineItem(
                          icon: entry.value.icon,
                          stepTitle: entry.value.title,
                          description: entry.value.description,
                          isDone: entry.key == 0 && _report.organ.isNotEmpty,
                          isLast: entry.key == workflowSteps.length - 1,
                        ),
                      ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            const SizedBox(height: 16),

            // Footer navigation buttons
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: ReclameJaColors.primaryYellow,
                foregroundColor: ReclameJaColors.textDark,
                minimumSize: const Size.fromHeight(52),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () {
                // Find Report in Store to get latest state and navigate
                final latestReport = ReportStore().allReports.firstWhere(
                      (r) => r.id == _report.id,
                      orElse: () => widget.report,
                    );
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) =>
                        ReportDetailScreen(report: latestReport),
                  ),
                );
              },
              icon: const Icon(Icons.receipt_long, size: 20),
              label: const Text('Acompanhar chamado',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () {
                // Back to main tab screen (pop back to HomeShell)
                Navigator.of(context).popUntil((route) => route.isFirst);
              },
              child: Text(
                'Voltar ao início',
                style: textTheme.labelLarge?.copyWith(
                    color: ReclameJaColors.secondaryEmerald,
                    fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  String get _statusBadge {
    if (_report.isOffline) return 'Aguardando envio';
    if (_isAnalysing) return 'Analisando…';
    if (_isClassificationConfirmed) return 'Classificação confirmada';
    if (_report.triageState == 'in_moderation') return 'Em revisão';
    return 'Classificado pela IA';
  }

  int get _urgencyLevel => _isAnalysing
      ? 0
      : switch (_report.urgency) {
          'alta' => 3,
          'media' => 2,
          'baixa' => 1,
          _ => 0,
        };

  Widget _buildTimelineItem({
    required IconData icon,
    required String stepTitle,
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
                  color: isDone
                      ? const Color(0xFFDCFCE7)
                      : ReclameJaColors.surfaceLow,
                  shape: BoxShape.circle,
                  border: Border.all(
                      color: isDone
                          ? const Color(0xFF86EFAC)
                          : ReclameJaColors.borderSlate),
                ),
                child: Icon(icon,
                    size: 16,
                    color: isDone
                        ? const Color(0xFF16A34A)
                        : ReclameJaColors.textMuted),
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
                  Text(stepTitle,
                      style: GoogleFonts.hankenGrotesk(
                          fontSize: 14, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: GoogleFonts.hankenGrotesk(
                        fontSize: 12,
                        color: ReclameJaColors.textMuted,
                        height: 1.3),
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

/// Escolha da categoria certa quando a sugestão da IA está errada.
class _CorrectClassificationDialog extends StatefulWidget {
  const _CorrectClassificationDialog();

  @override
  State<_CorrectClassificationDialog> createState() =>
      _CorrectClassificationDialogState();
}

class _CorrectClassificationDialogState
    extends State<_CorrectClassificationDialog> {
  ({String category, String subcategory})? _choice;

  @override
  Widget build(BuildContext context) {
    final choice = _choice;
    return AlertDialog(
      title: Text('Corrigir classificação',
          style: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.bold)),
      content: SizedBox(
        width: double.maxFinite,
        child: RadioGroup<({String category, String subcategory})>(
          groupValue: choice,
          onChanged: (value) => setState(() => _choice = value),
          child: ListView(
            shrinkWrap: true,
            children: [
              for (final category in reportCategories) ...[
                Padding(
                  padding: const EdgeInsets.only(top: 8, bottom: 2),
                  child: Text(labelForCategory(category),
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
                for (final subcategory in subcategoriesOf(category))
                  RadioListTile<({String category, String subcategory})>(
                    value: (category: category, subcategory: subcategory),
                    title: Text(labelForSubcategory(subcategory)),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
              ],
            ],
          ),
        ),
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
          onPressed:
              choice == null ? null : () => Navigator.pop(context, choice),
          child: const Text('Alterar categoria'),
        ),
      ],
    );
  }
}
