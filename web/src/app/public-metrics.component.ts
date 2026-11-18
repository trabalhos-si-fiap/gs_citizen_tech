import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface AgencyMetric {
  agency: { name: string };
  reports: number;
  avg_response_hours: number | null;
  resolution_rate: number | null;
}

interface MetricsResponse {
  totals: {
    reports: number;
    avg_response_hours: number | null;
    resolution_rate: number | null;
    recurrence: number;
  };
  by_agency: AgencyMetric[];
}

@Component({
  selector: 'app-public-metrics',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="public-metrics-page">
      <header class="metrics-heading">
        <div><span class="eyebrow">TRANSPARÊNCIA • DADOS AGREGADOS</span><h1>Indicadores públicos</h1><p>Dados agregados, sem identificação de cidadãos.</p></div>
        <div class="metrics-actions"><button class="button button-secondary" type="button" (click)="loadMetrics()" [disabled]="loading">{{ loading ? 'Atualizando…' : 'Atualizar' }}</button><button class="button button-green" type="button" (click)="downloadCsv()">Exportar CSV</button></div>
      </header>
      <section class="metrics-filters" aria-label="Filtros de indicadores"><label>Categoria<input type="text" [(ngModel)]="category" placeholder="risco_urbano" /></label><label>Órgão<input type="text" [(ngModel)]="agency" placeholder="agency_id" /></label><button class="button button-secondary" type="button" (click)="loadMetrics()" [disabled]="loading">Aplicar filtros</button></section>
      <p class="metrics-error" role="alert" *ngIf="errorMessage">{{ errorMessage }}</p>
      <section class="metrics-summary" aria-live="polite">
        <article><span>Reportes</span><strong>{{ data?.totals?.reports ?? '—' }}</strong></article>
        <article><span>Resposta média (h)</span><strong>{{ data?.totals?.avg_response_hours ?? '—' }}</strong></article>
        <article><span>Taxa de resolução</span><strong>{{ resolutionRateLabel }}</strong></article>
        <article><span>Recorrências</span><strong>{{ data?.totals?.recurrence ?? '—' }}</strong></article>
      </section>
      <section class="metrics-table-wrap">
        <table><thead><tr><th>Órgão</th><th>Reportes</th><th>Resposta média</th><th>Resolução</th></tr></thead><tbody><tr *ngFor="let row of data?.by_agency"><td>{{ row.agency.name }}</td><td>{{ row.reports }}</td><td>{{ row.avg_response_hours ?? '—' }}</td><td>{{ row.resolution_rate == null ? '—' : (row.resolution_rate * 100 | number:'1.1-1') + '%' }}</td></tr><tr *ngIf="!loading && data && data.by_agency.length === 0"><td colspan="4">Nenhum indicador encontrado para os filtros aplicados.</td></tr></tbody></table>
      </section>
      <p class="metrics-error" role="status" *ngIf="!loading && !errorMessage && !data">Aguardando dados da API pública de indicadores.</p>
    </section>
  `,
  styleUrl: './public-metrics.component.css',
})
export class PublicMetricsComponent implements OnInit {
  private readonly apiBase = (window as Window & { RECLAME_JA_API_URL?: string }).RECLAME_JA_API_URL ?? 'http://localhost:8000';
  category = '';
  agency = '';
  data: MetricsResponse | null = null;
  loading = false;
  errorMessage = '';

  get resolutionRateLabel(): string {
    const rate = this.data?.totals.resolution_rate;
    return rate == null ? '—' : `${(rate * 100).toFixed(1)}%`;
  }

  ngOnInit(): void {
    void this.loadMetrics();
  }

  async loadMetrics(): Promise<void> {
    this.loading = true;
    this.errorMessage = '';
    try {
      const response = await fetch(this.metricsUrl('json'));
      if (!response.ok) throw new Error(`API respondeu ${response.status}`);
      this.data = (await response.json()) as MetricsResponse;
    } catch (reason) {
      this.errorMessage = reason instanceof Error
        ? `Não foi possível carregar os indicadores (${reason.message}). Verifique a API e o CORS.`
        : 'Não foi possível carregar os indicadores. Verifique a API e o CORS.';
    } finally {
      this.loading = false;
    }
  }

  downloadCsv(): void {
    window.location.assign(this.metricsUrl('csv'));
  }

  private metricsUrl(format: 'json' | 'csv'): string {
    const params = new URLSearchParams();
    if (this.category.trim()) params.set('category', this.category.trim());
    if (this.agency.trim()) params.set('agency_id', this.agency.trim());
    params.set('format', format);
    return `${this.apiBase}/v1/public/metrics?${params.toString()}`;
  }
}
