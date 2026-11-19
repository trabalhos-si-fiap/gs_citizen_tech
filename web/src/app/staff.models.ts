export type ReportStatus = 'recebido' | 'encaminhado' | 'em_andamento' | 'resolvido';
export type ReportCategory = 'risco_urbano' | 'transporte_publico' | 'saude_atendimento' | 'a_classificar';

export interface AgencyRef {
  id: string;
  name: string;
}

export interface StaffReportItem {
  id: string;
  protocol: string;
  status: ReportStatus;
  category: ReportCategory | null;
  urgency: string | null;
  immediate_risk: boolean | null;
  description: string | null;
  lat: number;
  lon: number;
  received_at: string;
  deadline: string | null;
  overdue: boolean;
  agency: AgencyRef | null;
  confirmation_count: number;
}

export interface StaffReportPage {
  items: StaffReportItem[];
  next_cursor: string | null;
}

export interface StaffSummary {
  total: number;
  by_status: Record<ReportStatus, number>;
  overdue: number;
  due_soon: number;
}

export interface TimelineEvent {
  id: number;
  type: string;
  actor: string;
  justification: string | null;
  created_at: string;
}

export interface ReportDetail {
  id: string;
  protocol: string;
  status: ReportStatus;
  category: ReportCategory | null;
  lat: number;
  lon: number;
  received_at: string;
  group_id: string;
  confirmation_count: number;
  description: string | null;
  photo_url: string | null;
  anonymous: boolean;
  has_photo: boolean;
  triage_state: string;
  classification: {
    category: ReportCategory;
    subcategory: string | null;
    urgency: string | null;
    confidence: number;
    immediate_risk: boolean | null;
    model: string;
    source: string;
  } | null;
  agency: AgencyRef | null;
  deadline: string | null;
  timeline: TimelineEvent[];
}

export interface ReportSummary {
  id: string;
  protocol: string;
  status: ReportStatus;
  category: ReportCategory | null;
  lat: number;
  lon: number;
  received_at: string;
  group_id: string;
  confirmation_count: number;
}

export interface ReportListQuery {
  status?: ReportStatus | '';
  category?: ReportCategory | '';
  overdue?: boolean;
  q?: string;
  limit?: number;
  cursor?: string | null;
}

export interface StatusChange {
  action: 'in_progress' | 'resolved' | 'contest';
  deadline?: string;
  justification?: string;
}

export interface RedirectRequest {
  agency_id: string;
  justification: string;
  deadline?: string;
}

export interface ModerationRequest {
  justification: string;
  category?: ReportCategory;
  subcategory?: string;
}

export interface StaffAnalytics {
  period: { from: string; to: string; bucket: 'day' | 'week' };
  totals: { reports: number; resolved: number; open: number; overdue: number };
  timeseries: { period: string; opened: number; resolved: number }[];
  by_category: { category: ReportCategory; reports: number; resolved: number }[];
  by_agency: { agency: AgencyRef; reports: number; resolved: number; overdue: number; avg_resolution_hours: number | null }[];
  by_region: { region: string; lat: number; lon: number; reports: number; resolved: number }[];
}
