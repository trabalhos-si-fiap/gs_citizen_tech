import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { categoryLabel, deadlineLabel } from './labels';
import { StaffApiError, StaffApiService } from './staff-api.service';
import { StaffAnalytics, StaffReportItem } from './staff.models';

type PeriodKey = '7d' | '30d' | '12w';

const PERIODS: Record<PeriodKey, { label: string; days: number; bucket: 'day' | 'week' }> = {
  '7d': { label: 'Últimos 7 dias', days: 7, bucket: 'day' },
  '30d': { label: 'Últimos 30 dias', days: 30, bucket: 'day' },
  '12w': { label: 'Últimas 12 semanas', days: 84, bucket: 'week' },
};

const CHART = { width: 760, height: 240, left: 24, right: 736, top: 24, bottom: 210 };

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="dashboard-page">
      <div class="dashboard-heading">
        <div>
          <h1>Painel de controle</h1>
          <p>Reportes no seu escopo: aberturas, conclusões, prazos, categorias e regiões.</p>
        </div>
        <div class="heading-actions">
          <div class="date-tabs" aria-label="Período do painel">
            <button *ngFor="let key of periodKeys" type="button" [class.selected]="period() === key" (click)="selectPeriod(key)">{{ periods[key].label }}</button>
          </div>
          <button type="button" class="button button-spotlight" [disabled]="!analytics()" (click)="exportCsv()"><span class="material-symbols-outlined" aria-hidden="true">download</span> Exportar CSV</button>
        </div>
      </div>
      <p class="export-notice" role="alert" *ngIf="error()">{{ error() }}</p>

      <ng-container *ngIf="analytics() as a">
        <section class="summary-grid" aria-label="Indicadores operacionais">
          <article class="summary-card demand-card">
            <div class="summary-icon yellow-icon"><span class="material-symbols-outlined">pending_actions</span></div>
            <span class="eyebrow">REPORTES NO PERÍODO</span><strong>{{ a.totals.reports }}</strong>
            <div class="summary-foot"><small>{{ a.period.from | date: 'dd/MM' }} a {{ a.period.to | date: 'dd/MM' }}</small></div>
          </article>
          <article class="summary-card attendance-card">
            <div class="summary-icon blue-icon"><span class="material-symbols-outlined">local_shipping</span></div>
            <span class="eyebrow">EM ABERTO</span><strong>{{ a.totals.open }}</strong>
            <div class="summary-foot"><small>aguardando ou em atendimento</small></div>
          </article>
          <article class="summary-card critical-card">
            <div class="summary-icon red-icon"><span class="material-symbols-outlined">warning</span></div>
            <span class="eyebrow">PRAZO VENCIDO</span><strong class="critical-text">{{ a.totals.overdue }}</strong>
            <div class="summary-foot"><small>abertos depois do prazo</small></div>
          </article>
          <article class="summary-card resolution-card">
            <div class="summary-icon green-icon"><span class="material-symbols-outlined">task_alt</span></div>
            <span class="eyebrow">TAXA DE RESOLUÇÃO</span><strong class="green-text">{{ resolutionRate() }}</strong>
            <div class="summary-foot"><small>{{ a.totals.resolved }} resolvidos no período</small></div>
          </article>
        </section>

        <div class="dashboard-columns">
          <section class="chart-card" aria-labelledby="flow-title">
            <div class="card-heading">
              <div><h2 id="flow-title">Aberturas x conclusões</h2><p>Por {{ a.period.bucket === 'week' ? 'semana' : 'dia' }} no período selecionado</p></div>
              <div class="chart-legend"><span><i class="legend-yellow"></i>Novos reportes</span><span><i class="legend-green"></i>Resolvidos</span></div>
            </div>
            <div class="chart-area" role="img" [attr.aria-label]="chartLabel()">
              <div class="chart-grid"><span></span><span></span><span></span><span></span></div>
              <svg [attr.viewBox]="'0 0 ' + chart.width + ' ' + chart.height" preserveAspectRatio="none" aria-hidden="true">
                <defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#ebe100" stop-opacity=".42" /><stop offset="100%" stop-color="#ebe100" stop-opacity="0" /></linearGradient></defs>
                <path class="area-path" [attr.d]="series().area" />
                <path class="line-report" [attr.d]="series().opened" />
                <path class="line-resolution" [attr.d]="series().resolved" />
              </svg>
            </div>
            <div class="chart-days"><span *ngFor="let label of series().labels">{{ label }}</span></div>
            <div class="chart-callout"><span class="material-symbols-outlined">trending_up</span><span>Pico de {{ series().max }} reportes em um {{ a.period.bucket === 'week' ? 'semana' : 'dia' }}.<small>SALDO DO PERÍODO: {{ a.totals.resolved - a.totals.reports >= 0 ? '+' : '' }}{{ a.totals.resolved - a.totals.reports }}</small></span></div>
          </section>

          <aside class="alerts-card" aria-labelledby="alerts-title">
            <div class="section-title"><i></i><h2 id="alerts-title">Prazos vencidos</h2><span class="count-pill">{{ overdueItems().length }}</span></div>
            <a class="alert-item" *ngFor="let item of overdueItems()" [routerLink]="['/ocorrencias', item.id]">
              <span class="alert-thumb road"><span class="material-symbols-outlined">schedule</span></span>
              <span class="alert-copy"><small class="critical"><i></i> {{ deadlineLabel(item.deadline) }}</small><strong>{{ item.description || 'Reporte só com foto' }}</strong><small>{{ categoryLabel(item.category) }} • {{ item.agency?.name || 'Sem órgão' }}</small><span class="alert-meta">Protocolo {{ item.protocol }}</span></span>
            </a>
            <p *ngIf="overdueItems().length === 0">Nenhum reporte com prazo vencido.</p>
          </aside>

          <section class="detail-card neighborhood-card" id="regioes">
            <div class="card-heading"><div><h2>Regiões com mais reportes</h2><p>Células de ~1,2 km (sem base de bairros)</p></div><span class="material-symbols-outlined muted-icon">location_on</span></div>
            <ol class="district-list">
              <li *ngFor="let region of a.by_region.slice(0, 5); let i = index">
                <b>{{ (i + 1).toString().padStart(2, '0') }}</b>
                <span><a [href]="osm(region.lat, region.lon)" target="_blank" rel="noreferrer">{{ region.lat | number: '1.3-3' }}, {{ region.lon | number: '1.3-3' }}</a></span>
                <strong>{{ region.reports }}</strong>
              </li>
            </ol>
            <p *ngIf="a.by_region.length === 0">Sem reportes no período.</p>
          </section>

          <section class="detail-card service-card">
            <div class="card-heading"><div><h2>Categorias</h2><p>Proporção dos reportes do período</p></div><span class="material-symbols-outlined muted-icon">category</span></div>
            <div class="service-list">
              <div *ngFor="let item of a.by_category">
                <span><i class="service-mark emerald"></i>{{ categoryLabel(item.category) }}</span>
                <strong>{{ share(item.reports) }}% ({{ item.reports }})</strong>
                <span class="progress"><i [style.width.%]="share(item.reports)"></i></span>
              </div>
            </div>
          </section>

          <section class="detail-card service-card">
            <div class="card-heading"><div><h2>Órgãos</h2><p>Volume, atrasos e tempo médio de resolução</p></div><span class="material-symbols-outlined muted-icon">apartment</span></div>
            <div class="service-list">
              <div *ngFor="let item of a.by_agency">
                <span><i class="service-mark blue"></i>{{ item.agency.name }}</span>
                <strong>{{ item.reports }} • {{ item.overdue }} atrasados • {{ item.avg_resolution_hours !== null ? item.avg_resolution_hours + ' h' : '—' }}</strong>
                <span class="progress"><i [style.width.%]="share(item.reports)"></i></span>
              </div>
            </div>
          </section>
        </div>
      </ng-container>
      <p class="export-notice" *ngIf="!analytics() && !error()">Carregando…</p>
    </div>
  `,
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(StaffApiService);

  readonly periods = PERIODS;
  readonly periodKeys = Object.keys(PERIODS) as PeriodKey[];
  readonly chart = CHART;
  readonly categoryLabel = categoryLabel;
  readonly deadlineLabel = deadlineLabel;

  readonly period = signal<PeriodKey>('7d');
  readonly analytics = signal<StaffAnalytics | null>(null);
  readonly overdueItems = signal<StaffReportItem[]>([]);
  readonly error = signal('');

  readonly resolutionRate = computed(() => {
    const totals = this.analytics()?.totals;
    if (!totals || totals.reports === 0) return '—';
    return `${Math.round((totals.resolved / totals.reports) * 100)}%`;
  });

  /** Caminhos SVG das duas linhas, na mesma escala. */
  readonly series = computed(() => {
    const points = this.analytics()?.timeseries ?? [];
    const max = Math.max(1, ...points.map((p) => Math.max(p.opened, p.resolved)));
    const step = points.length > 1 ? (CHART.right - CHART.left) / (points.length - 1) : 0;
    const x = (i: number) => CHART.left + i * step;
    const y = (value: number) => CHART.bottom - (value / max) * (CHART.bottom - CHART.top);
    const line = (key: 'opened' | 'resolved') =>
      points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(' ');
    const opened = line('opened');
    const area = points.length ? `${opened} L${x(points.length - 1).toFixed(1)} ${CHART.bottom} L${CHART.left} ${CHART.bottom} Z` : '';
    const every = Math.max(1, Math.ceil(points.length / 8));
    const labels = points
      .filter((_, i) => i % every === 0)
      .map((p) => `${p.period.slice(8, 10)}/${p.period.slice(5, 7)}`);
    return { opened, resolved: line('resolved'), area, labels, max: Math.max(0, ...points.map((p) => p.opened)) };
  });

  readonly chartLabel = computed(() => {
    const totals = this.analytics()?.totals;
    return totals ? `Gráfico de aberturas e conclusões: ${totals.reports} abertos e ${totals.resolved} resolvidos no período` : 'Gráfico';
  });

  ngOnInit(): void {
    void this.load();
    void this.loadOverdue();
  }

  selectPeriod(key: PeriodKey): void {
    this.period.set(key);
    void this.load();
  }

  share(value: number): number {
    const total = this.analytics()?.totals.reports ?? 0;
    return total ? Math.round((value / total) * 100) : 0;
  }

  osm(lat: number, lon: number): string {
    return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=15/${lat}/${lon}`;
  }

  exportCsv(): void {
    const data = this.analytics();
    if (!data) return;
    const lines = ['periodo,abertos,resolvidos', ...data.timeseries.map((p) => `${p.period},${p.opened},${p.resolved}`)];
    lines.push('', 'categoria,reportes,resolvidos', ...data.by_category.map((c) => `${c.category},${c.reports},${c.resolved}`));
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `reclame-ja-painel-${data.period.from}-a-${data.period.to}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  private async load(): Promise<void> {
    const { days, bucket } = PERIODS[this.period()];
    const to = new Date();
    const from = new Date(to.getTime() - (days - 1) * 86_400_000);
    this.error.set('');
    try {
      this.analytics.set(await this.api.analytics({ from: isoDate(from), to: isoDate(to), bucket }));
    } catch (error) {
      this.error.set(error instanceof StaffApiError ? error.message : 'Falha ao carregar a analítica.');
    }
  }

  private async loadOverdue(): Promise<void> {
    try {
      this.overdueItems.set((await this.api.listReports({ overdue: true, limit: 4 })).items);
    } catch {
      this.overdueItems.set([]);
    }
  }
}
