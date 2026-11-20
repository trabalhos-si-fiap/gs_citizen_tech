import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  CATEGORY_ICONS,
  CATEGORY_LABELS,
  STATUS_LABELS,
  URGENCY_LABELS,
  categoryLabel,
  deadlineLabel,
  formatDateTime,
  locationLabel,
} from './labels';
import { StaffApiError, StaffApiService } from './staff-api.service';
import { ReportCategory, ReportStatus, StaffReportItem, StaffSummary } from './staff.models';

type StatusTab = ReportStatus | '';

const PAGE_SIZE = 25;

@Component({
  selector: 'app-occurrences',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="occurrences-page">
      <div class="occurrences-heading">
        <div>
          <div class="context-line"><span>MESA DE OPERAÇÕES</span><i></i><span>{{ scopeLabel }}</span></div>
          <h1>Gestão de Ocorrências</h1>
        </div>
        <span class="registered-count" *ngIf="summary() as s">{{ s.total }} reportes no seu escopo</span>
      </div>

      <section class="queue-stats" aria-label="Resumo das ocorrências" *ngIf="summary() as s">
        <article><span class="eyebrow">AGUARDANDO ATENDIMENTO</span><strong>{{ s.by_status.encaminhado }}</strong><span class="queue-icon yellow-icon"><span class="material-symbols-outlined">pending_actions</span></span></article>
        <article><span class="eyebrow">EM ANDAMENTO</span><strong class="blue-text">{{ s.by_status.em_andamento }}</strong><span class="queue-icon blue-icon"><span class="material-symbols-outlined">engineering</span></span></article>
        <article><span class="eyebrow">PRAZO EM RISCO</span><strong class="critical-text">{{ s.overdue }}</strong><small class="critical-text">atrasados • {{ s.due_soon }} vencem em 12h</small><span class="queue-icon red-icon"><span class="material-symbols-outlined">notification_important</span></span></article>
        <article><span class="eyebrow">RESOLVIDOS</span><strong class="green-text">{{ s.by_status.resolvido }}</strong><span class="queue-icon green-icon"><span class="material-symbols-outlined">task_alt</span></span></article>
      </section>

      <section class="filter-panel" aria-label="Filtros de ocorrências">
        <div class="filter-top">
          <form class="search-box" (ngSubmit)="reload()">
            <span class="material-symbols-outlined">search</span>
            <input type="search" name="search" [(ngModel)]="search" placeholder="Buscar protocolo, descrição ou endereço e tecle Enter" aria-label="Buscar ocorrências" />
          </form>
          <div class="status-tabs" aria-label="Filtrar por status">
            <button type="button" *ngFor="let tab of tabs" [class.selected]="status === tab.value" (click)="selectStatus(tab.value)">
              {{ tab.label }} <span *ngIf="tabCount(tab.value) as count">{{ count }}</span>
            </button>
          </div>
        </div>
        <div class="filter-bottom">
          <label><span class="eyebrow">CATEGORIA</span>
            <select [(ngModel)]="category" (ngModelChange)="reload()" aria-label="Filtrar por categoria">
              <option value="">Todas as categorias</option>
              <option *ngFor="let option of categories" [value]="option.value">{{ option.label }}</option>
            </select>
          </label>
          <label><span class="eyebrow">PRAZO</span>
            <select [(ngModel)]="overdueOnly" (ngModelChange)="reload()" aria-label="Filtrar por prazo">
              <option [ngValue]="false">Todos os prazos</option>
              <option [ngValue]="true">Somente atrasados</option>
            </select>
          </label>
          <button class="clear-filters" type="button" (click)="clearFilters()"><span class="material-symbols-outlined">filter_alt_off</span> Limpar filtros</button>
        </div>
      </section>

      <p class="feedback-message" role="alert" *ngIf="error()">{{ error() }} <button type="button" (click)="reload()">Tentar de novo</button></p>

      <section class="occurrence-table-wrap">
        <table class="occurrence-table">
          <thead><tr><th>PROTOCOLO</th><th>CATEGORIA</th><th>OCORRÊNCIA</th><th>LOCAL / ÓRGÃO</th><th>ABERTURA &amp; PRAZO</th><th>URGÊNCIA</th></tr></thead>
          <tbody>
            <tr *ngFor="let row of rows()">
              <td><a class="protocol-link" [routerLink]="['/ocorrencias', row.id]">{{ row.protocol }}</a><small>{{ statusLabels[row.status] }}</small></td>
              <td><span class="table-evidence road-evidence"><span class="material-symbols-outlined">{{ icon(row.category) }}</span><small>{{ row.confirmation_count }} confirm.</small></span></td>
              <td><a class="occurrence-title" [routerLink]="['/ocorrencias', row.id]">{{ row.description || 'Reporte só com foto' }}</a><div class="category-label"><span>{{ categoryLabel(row.category) }}</span><ng-container *ngIf="row.immediate_risk"> • risco imediato</ng-container></div></td>
              <td><strong class="address" [title]="locationLabel(row)">{{ locationLabel(row) }}</strong><small>{{ row.agency?.name || 'Sem órgão' }}</small></td>
              <td><span class="opened-time">{{ formatDateTime(row.received_at) }}</span><strong class="sla-time" [ngClass]="slaClass(row)">{{ deadlineLabel(row) }}</strong></td>
              <td><span class="priority-pill" [ngClass]="urgencyClass(row.urgency)"><i></i>{{ urgencyLabel(row.urgency) }}</span></td>
            </tr>
            <tr *ngIf="!loading() && rows().length === 0"><td class="empty-state" colspan="6">Nenhuma ocorrência corresponde aos filtros selecionados.</td></tr>
            <tr *ngIf="loading()"><td class="empty-state" colspan="6">Carregando…</td></tr>
          </tbody>
        </table>
        <footer class="table-footer">
          <span>Mostrando <strong>{{ rows().length }}</strong> ocorrências</span>
          <nav aria-label="Paginação"><button type="button" [disabled]="!nextCursor() || loading()" (click)="loadMore()">Carregar mais ›</button></nav>
        </footer>
      </section>
    </div>
  `,
  styleUrl: './occurrences.component.css',
})
export class OccurrencesComponent implements OnInit {
  private readonly api = inject(StaffApiService);

  readonly statusLabels = STATUS_LABELS;
  readonly categoryLabel = categoryLabel;
  readonly formatDateTime = formatDateTime;
  readonly locationLabel = locationLabel;
  readonly tabs: { value: StatusTab; label: string }[] = [
    { value: '', label: 'Todos' },
    { value: 'encaminhado', label: STATUS_LABELS.encaminhado },
    { value: 'em_andamento', label: STATUS_LABELS.em_andamento },
    { value: 'resolvido', label: STATUS_LABELS.resolvido },
  ];
  readonly categories = (Object.keys(CATEGORY_LABELS) as ReportCategory[]).map((value) => ({
    value,
    label: CATEGORY_LABELS[value],
  }));

  readonly rows = signal<StaffReportItem[]>([]);
  readonly summary = signal<StaffSummary | null>(null);
  readonly nextCursor = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');

  search = '';
  status: StatusTab = '';
  category: ReportCategory | '' = '';
  overdueOnly = false;
  scopeLabel = 'ESCOPO DO SERVIDOR';

  ngOnInit(): void {
    void this.loadSummary();
    void this.reload();
  }

  selectStatus(value: StatusTab): void {
    this.status = value;
    void this.reload();
  }

  tabCount(value: StatusTab): number | null {
    const summary = this.summary();
    if (!summary) return null;
    return value ? summary.by_status[value] : summary.total;
  }

  clearFilters(): void {
    this.search = '';
    this.status = '';
    this.category = '';
    this.overdueOnly = false;
    void this.reload();
  }

  async reload(): Promise<void> {
    this.rows.set([]);
    this.nextCursor.set(null);
    await this.fetch(null);
  }

  async loadMore(): Promise<void> {
    await this.fetch(this.nextCursor());
  }

  icon(category: ReportCategory | null): string {
    return category ? CATEGORY_ICONS[category] : 'help';
  }

  urgencyLabel(urgency: string | null): string {
    return urgency ? (URGENCY_LABELS[urgency] ?? urgency) : 'Não informada';
  }

  urgencyClass(urgency: string | null): string {
    return { alta: 'priority-critical', media: 'priority-medium', baixa: 'priority-low' }[urgency ?? ''] ?? 'priority-low';
  }

  deadlineLabel(row: StaffReportItem): string {
    if (row.status === 'resolvido') return 'Concluído';
    return deadlineLabel(row.deadline);
  }

  slaClass(row: StaffReportItem): string {
    if (row.status === 'resolvido') return 'safe';
    if (row.overdue) return 'danger';
    return row.deadline && new Date(row.deadline).getTime() - Date.now() < 12 * 3_600_000 ? 'warning' : 'safe';
  }

  private async loadSummary(): Promise<void> {
    try {
      this.summary.set(await this.api.summary());
    } catch {
      // O resumo é complementar; a lista mostra o erro principal.
    }
  }

  private async fetch(cursor: string | null): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const page = await this.api.listReports({
        status: this.status,
        category: this.category,
        overdue: this.overdueOnly,
        q: this.search,
        limit: PAGE_SIZE,
        cursor,
      });
      this.rows.update((rows) => [...rows, ...page.items]);
      this.nextCursor.set(page.next_cursor);
    } catch (error) {
      this.error.set(error instanceof StaffApiError ? error.message : 'Falha ao carregar as ocorrências.');
    } finally {
      this.loading.set(false);
    }
  }
}
