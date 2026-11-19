import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { API_BASE } from './api.config';
import {
  AgencyRef,
  ModerationRequest,
  RedirectRequest,
  ReportDetail,
  ReportListQuery,
  ReportSummary,
  StaffAnalytics,
  StaffReportPage,
  StaffSummary,
  StatusChange,
} from './staff.models';

/** Erro de uma chamada ao backend, com mensagem pronta para a tela. */
export class StaffApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const STAFF = `${API_BASE}/v1/staff`;

@Injectable({ providedIn: 'root' })
export class StaffApiService {
  private readonly http = inject(HttpClient);

  listReports(query: ReportListQuery): Promise<StaffReportPage> {
    let params = new HttpParams().set('limit', String(query.limit ?? 25));
    if (query.status) params = params.set('status', query.status);
    if (query.category) params = params.set('category', query.category);
    if (query.overdue) params = params.set('overdue', 'true');
    if (query.q?.trim()) params = params.set('q', query.q.trim());
    if (query.cursor) params = params.set('cursor', query.cursor);
    return this.call(this.http.get<StaffReportPage>(`${STAFF}/reports`, { params }));
  }

  summary(): Promise<StaffSummary> {
    return this.call(this.http.get<StaffSummary>(`${STAFF}/summary`));
  }

  detail(id: string): Promise<ReportDetail> {
    return this.call(this.http.get<ReportDetail>(`${STAFF}/reports/${encodeURIComponent(id)}`));
  }

  changeStatus(id: string, change: StatusChange): Promise<ReportDetail> {
    return this.call(this.http.post<ReportDetail>(`${STAFF}/reports/${encodeURIComponent(id)}/status`, change));
  }

  redirect(id: string, request: RedirectRequest): Promise<ReportDetail> {
    return this.call(this.http.post<ReportDetail>(`${STAFF}/reports/${encodeURIComponent(id)}/redirect`, request));
  }

  /** Todos os órgãos da matriz: destinos possíveis de um redirecionamento. */
  async redirectTargets(): Promise<AgencyRef[]> {
    const response = await this.call(
      this.http.get<{ items: AgencyRef[] }>(`${STAFF}/agencies`, { params: { scope: 'all' } }),
    );
    return response.items;
  }

  moderationQueue(limit = 50): Promise<{ items: ReportSummary[]; count: number }> {
    return this.call(this.http.get<{ items: ReportSummary[]; count: number }>(`${STAFF}/moderation`, { params: { limit } }));
  }

  moderate(id: string, decision: 'approve' | 'reject', request: ModerationRequest): Promise<ReportDetail> {
    return this.call(
      this.http.post<ReportDetail>(`${STAFF}/moderation/${encodeURIComponent(id)}/${decision}`, request),
    );
  }

  analytics(params: { from?: string; to?: string; bucket?: 'day' | 'week' }): Promise<StaffAnalytics> {
    let query = new HttpParams();
    if (params.from) query = query.set('from', params.from);
    if (params.to) query = query.set('to', params.to);
    if (params.bucket) query = query.set('bucket', params.bucket);
    return this.call(this.http.get<StaffAnalytics>(`${STAFF}/analytics`, { params: query }));
  }

  private async call<T>(request: import('rxjs').Observable<T>): Promise<T> {
    try {
      return await firstValueFrom(request);
    } catch (error) {
      throw toStaffApiError(error);
    }
  }
}

export function toStaffApiError(error: unknown): StaffApiError {
  if (!(error instanceof HttpErrorResponse)) return new StaffApiError(0, 'Erro inesperado. Tente novamente.');
  if (error.status === 0) return new StaffApiError(0, 'Sem conexão com o servidor. Verifique a rede e tente novamente.');
  const body = error.error as { error?: { message?: string }; detail?: string } | null;
  const message = body?.error?.message ?? body?.detail;
  if (typeof message === 'string' && message) return new StaffApiError(error.status, message);
  const fallback: Record<number, string> = {
    403: 'Seu perfil não tem acesso a esta ação.',
    404: 'Reporte não encontrado no seu escopo.',
    409: 'Esta ação não é permitida no estado atual do reporte.',
    422: 'Dados inválidos. Revise os campos.',
  };
  return new StaffApiError(error.status, fallback[error.status] ?? 'Falha no servidor. Tente novamente.');
}
