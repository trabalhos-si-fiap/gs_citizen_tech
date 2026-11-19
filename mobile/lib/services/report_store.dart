import 'dart:async';

class ReportEvent {
  final String title;
  final String time;
  final String desc;
  final String actor;

  ReportEvent({
    required this.title,
    required this.time,
    required this.desc,
    required this.actor,
  });
}

class Report {
  final String id;
  final String? apiId;
  final String title;
  final String description;
  final String location;
  final String details;
  final String category;
  final String subcategory;
  final String status; // 'Recebido', 'Encaminhado', 'Em andamento', 'Resolvido'
  final String organ;
  final int confirmationCount;
  final bool isUserConfirmed;
  final String clientCreatedAt;
  final bool isOffline;
  final String? imageUrl;
  final String forecast;
  final List<ReportEvent> timeline;
  final List<Map<String, String>> comments;

  Report({
    required this.id,
    this.apiId,
    required this.title,
    required this.description,
    required this.location,
    required this.details,
    required this.category,
    required this.subcategory,
    required this.status,
    required this.organ,
    required this.confirmationCount,
    this.isUserConfirmed = false,
    required this.clientCreatedAt,
    this.isOffline = false,
    this.imageUrl,
    required this.forecast,
    required this.timeline,
    required this.comments,
  });

  Report copyWith({
    String? id,
    String? apiId,
    String? title,
    String? description,
    String? location,
    String? details,
    String? category,
    String? subcategory,
    String? status,
    String? organ,
    int? confirmationCount,
    bool? isUserConfirmed,
    String? clientCreatedAt,
    bool? isOffline,
    String? imageUrl,
    String? forecast,
    List<ReportEvent>? timeline,
    List<Map<String, String>>? comments,
  }) {
    return Report(
      id: id ?? this.id,
      apiId: apiId ?? this.apiId,
      title: title ?? this.title,
      description: description ?? this.description,
      location: location ?? this.location,
      details: details ?? this.details,
      category: category ?? this.category,
      subcategory: subcategory ?? this.subcategory,
      status: status ?? this.status,
      organ: organ ?? this.organ,
      confirmationCount: confirmationCount ?? this.confirmationCount,
      isUserConfirmed: isUserConfirmed ?? this.isUserConfirmed,
      clientCreatedAt: clientCreatedAt ?? this.clientCreatedAt,
      isOffline: isOffline ?? this.isOffline,
      imageUrl: imageUrl ?? this.imageUrl,
      forecast: forecast ?? this.forecast,
      timeline: timeline ?? this.timeline,
      comments: comments ?? this.comments,
    );
  }
}

class ReportStore {
  static final ReportStore _instance = ReportStore._internal();
  factory ReportStore() => _instance;

  ReportStore._internal() {
    if (const bool.fromEnvironment('USE_DEMO_REPORTS')) {
      initializeMockDataForDemo();
    }
  }

  final _reportsController = StreamController<List<Report>>.broadcast();
  Stream<List<Report>> get reportsStream => _reportsController.stream;

  final List<Report> _reports = [];

  List<Report> get allReports => List.unmodifiable(_reports);

  void replaceFromApi(List<Map<String, dynamic>> items) {
    final reports = items.map(_reportFromApi).toList();
    final pending = _reports.where((report) => report.isOffline).toList();
    _reports
      ..clear()
      ..addAll(reports)
      ..addAll(pending);
    _notify();
  }

  void upsertFromApi(Map<String, dynamic> item) {
    final report = _reportFromApi(item);
    final index = _reports.indexWhere(
      (existing) => existing.apiId == report.apiId,
    );
    if (index == -1) {
      _reports.insert(0, report);
    } else {
      _reports[index] = report;
    }
    _notify();
  }

  void removeByApiId(String apiId) {
    _reports.removeWhere((report) => report.apiId == apiId);
    _notify();
  }

  void updateComments(String apiId, List<Map<String, String>> comments) {
    final index = _reports.indexWhere((report) => report.apiId == apiId);
    if (index == -1) return;
    _reports[index] = _reports[index].copyWith(comments: comments);
    _notify();
  }

  void updateConfirmationCount(String apiId, int count) {
    final index = _reports.indexWhere((report) => report.apiId == apiId);
    if (index == -1) return;
    _reports[index] = _reports[index].copyWith(
      confirmationCount: count,
      isUserConfirmed: true,
    );
    _notify();
  }

  Report _reportFromApi(Map<String, dynamic> item) {
    final category = item['category']?.toString() ?? 'a_classificar';
    final receivedAt = DateTime.tryParse(
          item['received_at']?.toString() ?? '',
        ) ??
        DateTime.now();
    final status = switch (item['status']?.toString()) {
      'encaminhado' => 'Encaminhado',
      'em_andamento' => 'Em andamento',
      'resolvido' => 'Resolvido',
      _ => 'Recebido',
    };
    final rawTimeline = item['timeline'];
    var forwardedBefore = false;
    final timeline = rawTimeline is List
        ? rawTimeline.whereType<Map>().map((event) {
            final date = DateTime.tryParse(
                  _asUtcIso(event['created_at']?.toString() ?? ''),
                ) ??
                receivedAt;
            final type = event['type']?.toString() ?? '';
            // Um segundo "encaminhado" é um redirecionamento entre órgãos.
            final title = type == 'encaminhado' && forwardedBefore
                ? 'Redirecionado a outro órgão'
                : _eventTitles[type] ?? 'Atualização';
            if (type == 'encaminhado') forwardedBefore = true;
            return ReportEvent(
              title: title,
              time: _formatDateTime(date),
              desc: event['justification']?.toString() ?? '',
              actor: _actorLabel(event['actor']?.toString() ?? ''),
            );
          }).toList()
        : <ReportEvent>[];
    final classification = item['classification'];
    final subcategory = classification is Map
        ? classification['subcategory']?.toString() ?? ''
        : '';
    final deadline = DateTime.tryParse(
      _asUtcIso(item['deadline']?.toString() ?? ''),
    );
    final photo = item['photo_url']?.toString();
    return Report(
      id: item['protocol']?.toString() ?? item['id'].toString(),
      apiId: item['id']?.toString(),
      title: (item['description']?.toString().trim().isNotEmpty ?? false)
          ? item['description'].toString()
          : 'Ocorrência urbana',
      description: item['description']?.toString() ?? '',
      location: '${item['lat'] ?? ''}, ${item['lon'] ?? ''}',
      details: '',
      category: category,
      subcategory: _humanize(subcategory),
      status: status,
      organ: item['agency'] is Map
          ? (item['agency'] as Map)['name']?.toString() ?? ''
          : '',
      confirmationCount: (item['confirmation_count'] as num?)?.toInt() ?? 0,
      clientCreatedAt: receivedAt.toLocal().toString(),
      imageUrl: photo,
      forecast: deadline == null ? '' : 'Prazo: ${_formatDateTime(deadline)}',

      timeline: timeline,
      comments: const [],
    );
  }

  void initializeMockDataForDemo() {
    _reports.addAll([
      Report(
        id: '#CV-2023-8941',
        title: 'Cratera no asfalto com risco a pedestres e ciclistas',
        description:
            'Grande buraco aberto na pista da direita após a chuva forte, oferecendo risco de queda a ciclistas e pedestres no cruzamento.',
        location: 'Rua das Palmeiras, 340',
        details: 'Jardim das Flores, São Paulo - SP',
        category: 'Risco Urbano',
        subcategory: 'Pavimentação',
        status: 'Em andamento',
        organ: 'Secretaria Municipal de Infraestrutura Urbana e Obras (SIURB)',
        confirmationCount: 12,
        isUserConfirmed: false,
        clientCreatedAt: '18/10/2026',
        imageUrl:
            'https://lh3.googleusercontent.com/aida-public/AB6AXuCIe4nA0gwvKNtMa9Zt8wmPBk8EQDNw3_keZlUqoHaQ4UfsLnJ3GyTyJh2sLgomyhQMoNVdKozxKhDPoho6ahRq132VhCJCqLE79r-jxEEi5fFOOWjsFdWidSPNxQLv2FxbDZFQwG8nwPnJde0MDrgkeS6r20meg8c_VJA2Zg3DAo3IyPuMk46_FGYHSQWXj540cNotDDLaapBQuGeAFVEElVDOe9nEhLrr2BBuypov',
        forecast: 'Conclusão até 24 de Outubro (em 48h úteis)',
        timeline: [
          ReportEvent(
              title: 'Recebido',
              time: '18/10 às 09:14',
              desc:
                  'Cadastrado e validado pelo Sistema Central de Zeladoria Urbana.',
              actor: 'Sistema'),
          ReportEvent(
              title: 'Encaminhado',
              time: '18/10 às 11:30',
              desc:
                  'Despachado para a Secretaria de Infraestrutura Urbana e Obras (SIURB).',
              actor: 'Sistema'),
          ReportEvent(
              title: 'Em andamento',
              time: '19/10 às 08:45',
              desc:
                  'Equipe técnica em deslocamento para vistoria e fechamento preventivo do perímetro da pista.',
              actor: 'SIURB - Equipe Operacional Sul 4'),
        ],
        comments: [
          {
            'author': 'SIURB Oficial',
            'time': 'Hoje às 14:00',
            'text':
                'Sinalização emergencial com cavaletes refletivos instalada preventivamente para desvio do fluxo. A equipe de asfalto chega nas primeiras horas de amanhã.',
            'isOfficial': 'true'
          },
          {
            'author': 'Marcos S. (morador)',
            'time': 'Ontem às 17:22',
            'text':
                'Agradeço o retorno rápido do protocolo. O trânsito de motos nesta esquina estava perigoso por causa da profundidade do buraco.',
            'isOfficial': 'false'
          },
          {
            'author': 'Ana Cláudia V.',
            'time': '18/10 às 15:40',
            'text':
                'Confirmei o chamado também! Moro no prédio em frente e quase presenciei uma queda de bicicleta hoje de manhã.',
            'isOfficial': 'false'
          },
        ],
      ),
      Report(
        id: '#CV-2023-5510',
        title: 'Ônibus linha 2023 com atraso crônico e abrigo quebrado',
        description:
            'Os ônibus desta linha atrasam mais de 40 minutos todas as manhãs. Além disso, o abrigo no ponto está totalmente vandalizado, sem cobertura.',
        location: 'Parada Hospital Geral',
        details: 'Avenida das Nações, 1050 - Jardim das Flores',
        category: 'Transporte',
        subcategory: 'Atendimento e Abrigos',
        status: 'Recebido',
        organ: 'SPTrans / Operadora Distrital de Transportes',
        confirmationCount: 8,
        isUserConfirmed: false,
        clientCreatedAt: '15/10/2026',
        imageUrl:
            'https://lh3.googleusercontent.com/aida-public/AB6AXuCnllQuuY7jIxXn-WXt0z-wk0L_Y5gQvkpyAgPAwyyqD77-x8y9k_l7KpfaK_UBhzdXflHSROd7vlugQjlg9L77OSA_X5wx3OWROwbMS9v5ERa_apo_py2JFThXW9paXyD4UOf0KPFBpDHpz-Sf3BnS9gAwSIb5WPWqc49X579GKJHg0RKoGNJ9cAJJm7ej02qrtQ_CiKYYvOXpJGvN4u0lhEVq23z8-muEXMTFSnKO',
        forecast: 'Resposta prevista em até 5 dias úteis',
        timeline: [
          ReportEvent(
              title: 'Recebido',
              time: '15/10 às 08:30',
              desc:
                  'Ocorrência registrada no banco de dados e aguardando encaminhamento automático à operadora.',
              actor: 'Sistema'),
        ],
        comments: [
          {
            'author': 'Mariana (Você)',
            'time': '15/10 às 08:32',
            'text':
                'Todo dia de chuva é um sofrimento sem a cobertura do ponto. Esperamos providências rápidas!',
            'isOfficial': 'false'
          },
        ],
      ),
      Report(
        id: '#CV-2023-1122',
        title: 'Lâmpada queimada na Praça da Matriz',
        description:
            'Três postes consecutivos estão apagados no lado leste da praça, deixando o local totalmente às escuras à noite e gerando insegurança.',
        location: 'Praça da Matriz, Lado Leste',
        details: 'Jardim das Flores, São Paulo - SP',
        category: 'Risco Urbano',
        subcategory: 'Iluminação Pública',
        status: 'Resolvido',
        organ: 'Ilume / Departamento de Iluminação Pública',
        confirmationCount: 23,
        isUserConfirmed: true,
        clientCreatedAt: '10/10/2026',
        imageUrl: null,
        forecast: 'Resolvido em 12/10/2026',
        timeline: [
          ReportEvent(
              title: 'Recebido',
              time: '10/10 às 20:15',
              desc: 'Registrado via aplicativo Voz Cidadã.',
              actor: 'Sistema'),
          ReportEvent(
              title: 'Encaminhado',
              time: '11/10 às 09:00',
              desc: 'Enviado à central técnica da Ilume.',
              actor: 'Sistema'),
          ReportEvent(
              title: 'Em andamento',
              time: '11/10 às 14:00',
              desc:
                  'Equipe de manutenção elétrica despachada para substituição de lâmpadas de vapor de sódio por LED.',
              actor: 'Ilume - Equipe Distrital Leste'),
          ReportEvent(
              title: 'Resolvido',
              time: '12/10 às 18:30',
              desc:
                  'Lâmpadas substituídas por luminárias de LED modernas e potentes. Circuito testado e ativo.',
              actor: 'Ilume - Equipe Distrital Leste'),
        ],
        comments: [
          {
            'author': 'Ilume Oficial',
            'time': '12/10 às 18:35',
            'text':
                'Manutenção corretiva e preventiva finalizada. Três pontos de iluminação restaurados com lâmpadas LED de 150W. Agradecemos a colaboração!',
            'isOfficial': 'true'
          },
        ],
      ),
    ]);
    _notify();
  }

  void addReport(Report report) {
    _reports.insert(0, report);
    _notify();
  }

  void updateReportStatus(String id, String newStatus, ReportEvent event) {
    final idx = _reports.indexWhere((r) => r.id == id);
    if (idx != -1) {
      final r = _reports[idx];
      final List<ReportEvent> updatedTimeline = List.from(r.timeline)
        ..add(event);
      _reports[idx] = r.copyWith(status: newStatus, timeline: updatedTimeline);
      _notify();
    }
  }

  void toggleUserConfirmation(String id) {
    final idx = _reports.indexWhere((r) => r.id == id);
    if (idx != -1) {
      final r = _reports[idx];
      final isConfirmed = !r.isUserConfirmed;
      final newCount =
          isConfirmed ? r.confirmationCount + 1 : r.confirmationCount - 1;
      _reports[idx] = r.copyWith(
        isUserConfirmed: isConfirmed,
        confirmationCount: newCount,
      );
      _notify();
    }
  }

  void addComment(String id, Map<String, String> comment) {
    final idx = _reports.indexWhere((r) => r.id == id);
    if (idx != -1) {
      final r = _reports[idx];
      final List<Map<String, String>> updatedComments = List.from(r.comments)
        ..add(comment);
      _reports[idx] = r.copyWith(comments: updatedComments);
      _notify();
    }
  }

  void _notify() {
    _reportsController.add(List.unmodifiable(_reports));
  }
}


const _eventTitles = {
  'recebido': 'Reporte recebido',
  'classificado': 'Classificado automaticamente',
  'classificacao_confirmada': 'Classificação confirmada',
  'classificacao_corrigida': 'Classificação corrigida',
  'encaminhado': 'Encaminhado ao órgão',
  'em_andamento': 'Atendimento iniciado',
  'resolvido': 'Resolvido',
  'reaberto': 'Reaberto',
  'contestado': 'Contestado pelo órgão',
  'enviado_moderacao': 'Em análise pela moderação',
  'vinculado_grupo': 'Agrupado a um reporte igual',
  'confirmacao_adicionada': 'Outro cidadão confirmou',
  'cobrado': 'Você cobrou o órgão',
  'sinalizado': 'Sinalizado para revisão',
  'moderacao_aprovada': 'Aprovado pela moderação',
  'moderacao_rejeitada': 'Recusado pela moderação',
};

String _actorLabel(String actor) {
  if (actor.isEmpty || actor == 'system') return 'Sistema';
  if (actor.startsWith('agency')) return 'Órgão responsável';
  if (actor.startsWith('citizen')) return 'Cidadão';
  if (actor.startsWith('moderator') || actor.startsWith('admin')) {
    return 'Moderação';
  }
  if (actor.startsWith('manager')) return 'Gestão municipal';
  return 'Prefeitura';
}

/// O backend devolve alguns horários sem fuso; eles estão em UTC.
String _asUtcIso(String value) {
  if (value.isEmpty) return value;
  final hasZone = value.endsWith('Z') ||
      RegExp(r'[+-]\d{2}:?\d{2}$').hasMatch(value);
  return hasZone ? value : '${value}Z';
}

String _formatDateTime(DateTime value) {
  final local = value.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year} '
      '${two(local.hour)}:${two(local.minute)}';
}

String _humanize(String code) {
  if (code.isEmpty || code == 'a_classificar') return '';
  final text = code.replaceAll('_', ' ');
  return text[0].toUpperCase() + text.substring(1);
}
