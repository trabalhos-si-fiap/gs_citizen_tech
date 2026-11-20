/// Rótulos legíveis dos códigos de categoria e subcategoria da API
/// (taxonomia em `back-end/app/seeds/taxonomy.json`).
library;

/// Mesmos rótulos dos chips de filtro do mapa e do feed.
const Map<String, String> _categoryLabels = {
  'risco_urbano': 'Risco Urbano',
  'transporte_publico': 'Transporte',
  'saude_atendimento': 'Saúde',
};

/// Subcategorias de cada categoria, com o rótulo exibido.
const Map<String, Map<String, String>> _subcategoryLabels = {
  'risco_urbano': {
    'arvore_risco': 'Árvore com risco de queda',
    'esgoto_vazamento': 'Esgoto e vazamento',
    'calcada_danificada': 'Calçada danificada',
    'iluminacao_falha': 'Falha na iluminação',
    'buraco_via': 'Buraco na via',
    'alagamento': 'Alagamento',
  },
  'transporte_publico': {
    'falha_trem_metro': 'Falha no trem ou metrô',
    'onibus_atraso_lotacao': 'Ônibus atrasado ou lotado',
    'ponto_onibus_danificado': 'Ponto de ônibus danificado',
    'acessibilidade_estacao': 'Acessibilidade na estação',
  },
  'saude_atendimento': {
    'falta_medicamento': 'Falta de medicamento',
    'falta_medico': 'Falta de médico',
    'demora_atendimento': 'Demora no atendimento',
    'estrutura_unidade': 'Estrutura da unidade de saúde',
  },
};

/// Categorias que o munícipe pode escolher ao corrigir a classificação.
Iterable<String> get reportCategories => _subcategoryLabels.keys;

/// Subcategorias da [category] (códigos da API).
Iterable<String> subcategoriesOf(String category) =>
    _subcategoryLabels[category]?.keys ?? const [];

/// Rótulo da categoria; sem categoria (ou ainda não classificada) vira
/// "A classificar".
String labelForCategory(String? category) {
  if (category == null || category.isEmpty || category == 'a_classificar') {
    return 'A classificar';
  }
  return _categoryLabels[category] ?? _humanize(category);
}

/// Rótulo da subcategoria; vazio quando não há subcategoria.
String labelForSubcategory(String? subcategory) {
  if (subcategory == null ||
      subcategory.isEmpty ||
      subcategory == 'a_classificar') {
    return '';
  }
  for (final labels in _subcategoryLabels.values) {
    final label = labels[subcategory];
    if (label != null) return label;
  }
  return _humanize(subcategory);
}

/// Urgência estimada pela IA: baixa, media ou alta.
String labelForUrgency(String? urgency) => switch (urgency) {
      'alta' => 'Alta',
      'media' => 'Média',
      'baixa' => 'Baixa',
      _ => 'Não informada',
    };

/// Código desconhecido continua legível: "poste_caido" → "Poste caido".
String _humanize(String code) {
  final text = code.replaceAll('_', ' ');
  return text[0].toUpperCase() + text.substring(1);
}
