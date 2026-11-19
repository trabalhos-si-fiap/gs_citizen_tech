import { ReportCategory, ReportStatus } from './staff.models';

export const STATUS_LABELS: Record<ReportStatus, string> = {
  recebido: 'Recebido',
  encaminhado: 'Aguardando atendimento',
  em_andamento: 'Em andamento',
  resolvido: 'Resolvido',
};

export const CATEGORY_LABELS: Record<ReportCategory, string> = {
  risco_urbano: 'Risco urbano',
  transporte_publico: 'Transporte público',
  saude_atendimento: 'Saúde',
  a_classificar: 'A classificar',
};

export const CATEGORY_ICONS: Record<ReportCategory, string> = {
  risco_urbano: 'warning',
  transporte_publico: 'directions_bus',
  saude_atendimento: 'local_hospital',
  a_classificar: 'help',
};

export const URGENCY_LABELS: Record<string, string> = {
  alta: 'Alta',
  media: 'Média',
  baixa: 'Baixa',
};

export const EVENT_LABELS: Record<string, string> = {
  recebido: 'Reporte recebido',
  classificado: 'Classificado automaticamente',
  classificacao_confirmada: 'Classificação confirmada',
  classificacao_corrigida: 'Classificação corrigida',
  encaminhado: 'Encaminhado ao órgão',
  em_andamento: 'Atendimento iniciado',
  resolvido: 'Resolvido',
  reaberto: 'Reaberto pelo cidadão',
  contestado: 'Contestado pelo órgão',
  enviado_moderacao: 'Enviado à moderação',
  vinculado_grupo: 'Agrupado a um reporte igual',
  confirmacao_adicionada: 'Outro cidadão confirmou',
  cobrado: 'Cidadão cobrou o órgão',
  sinalizado: 'Sinalizado por um cidadão',
  moderacao_aprovada: 'Aprovado na moderação',
  moderacao_rejeitada: 'Rejeitado na moderação',
};

export function categoryLabel(category: ReportCategory | null | undefined): string {
  return category ? CATEGORY_LABELS[category] : 'Sem categoria';
}

export function subcategoryLabel(subcategory: string | null | undefined): string {
  if (!subcategory) return '';
  const text = subcategory.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`);
  return date.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** "faltam 5h", "atrasado 2h"; o backend devolve prazos em UTC. */
export function deadlineLabel(deadline: string | null | undefined, now = Date.now()): string {
  if (!deadline) return 'Sem prazo';
  const target = new Date(deadline.endsWith('Z') || deadline.includes('+') ? deadline : `${deadline}Z`).getTime();
  const hours = Math.round((target - now) / 3_600_000);
  if (hours >= 48) return `faltam ${Math.round(hours / 24)} dias`;
  if (hours >= 0) return `faltam ${hours}h`;
  if (hours > -48) return `atrasado ${-hours}h`;
  return `atrasado ${Math.round(-hours / 24)} dias`;
}
