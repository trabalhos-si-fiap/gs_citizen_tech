import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { STATUS_LABELS, categoryLabel, formatDateTime } from './labels';
import { StaffApiError, StaffApiService } from './staff-api.service';
import { ReportSummary } from './staff.models';

@Component({
  selector: 'app-moderation',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="occurrences-page">
      <div class="occurrences-heading">
        <div>
          <div class="context-line"><span>MODERAÇÃO</span><i></i><span>SINALIZAÇÕES E CASOS SEM ÓRGÃO</span></div>
          <h1>Fila de moderação</h1>
        </div>
        <span class="registered-count">{{ items().length }} na fila</span>
      </div>

      <p class="feedback-message" role="alert" *ngIf="error()">{{ error() }}</p>

      <section class="occurrence-table-wrap">
        <table class="occurrence-table">
          <thead><tr><th>PROTOCOLO</th><th>CATEGORIA</th><th>STATUS</th><th>RECEBIDO</th><th>CONFIRMAÇÕES</th></tr></thead>
          <tbody>
            <tr *ngFor="let item of items()">
              <td><a class="protocol-link" [routerLink]="['/ocorrencias', item.id]">{{ item.protocol }}</a><small>Abrir para aprovar ou rejeitar</small></td>
              <td>{{ categoryLabel(item.category) }}</td>
              <td>{{ statusLabels[item.status] }}</td>
              <td>{{ formatDateTime(item.received_at) }}</td>
              <td>{{ item.confirmation_count }}</td>
            </tr>
            <tr *ngIf="!loading() && items().length === 0"><td class="empty-state" colspan="5">Nenhum reporte aguardando moderação.</td></tr>
            <tr *ngIf="loading()"><td class="empty-state" colspan="5">Carregando…</td></tr>
          </tbody>
        </table>
      </section>
    </div>
  `,
  styleUrl: './occurrences.component.css',
})
export class ModerationComponent implements OnInit {
  private readonly api = inject(StaffApiService);

  readonly statusLabels = STATUS_LABELS;
  readonly categoryLabel = categoryLabel;
  readonly formatDateTime = formatDateTime;
  readonly items = signal<ReportSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  async ngOnInit(): Promise<void> {
    try {
      this.items.set((await this.api.moderationQueue(100)).items);
    } catch (error) {
      this.error.set(error instanceof StaffApiError ? error.message : 'Falha ao carregar a fila.');
    } finally {
      this.loading.set(false);
    }
  }
}
