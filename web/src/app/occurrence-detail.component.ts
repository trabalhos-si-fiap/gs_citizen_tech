import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from './auth.service';
import {
  CATEGORY_LABELS,
  EVENT_LABELS,
  STATUS_LABELS,
  URGENCY_LABELS,
  categoryLabel,
  deadlineLabel,
  formatDateTime,
  subcategoryLabel,
  toDateTimeLocal,
} from './labels';
import { StaffApiError, StaffApiService } from './staff-api.service';
import { AgencyRef, ReportCategory, ReportDetail, StatusChange } from './staff.models';

@Component({
  selector: 'app-occurrence-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="detail-page">
      <div class="detail-toolbar">
        <div class="breadcrumbs">
          <a routerLink="/ocorrencias"><span class="material-symbols-outlined">arrow_back</span> Voltar à lista</a>
          <span>/</span><span>Gestão de reportes</span><span>/</span><strong *ngIf="report() as r">#{{ r.protocol }}</strong>
        </div>
      </div>

      <p class="feedback-message" role="alert" *ngIf="loadError()">{{ loadError() }}</p>
      <p class="feedback-message" *ngIf="!report() && !loadError()">Carregando…</p>

      <ng-container *ngIf="report() as r">
        <section class="incident-hero">
          <div class="incident-main">
            <div class="incident-tags">
              <span class="status-chip status-analysis"><i></i> {{ statusLabels[r.status] }}</span>
              <span class="status-chip status-priority" *ngIf="r.classification?.urgency as urgency"><span class="material-symbols-outlined">warning</span> Urgência {{ urgencyLabel(urgency) }}</span>
              <span class="status-chip status-category"><span class="material-symbols-outlined">alt_route</span> {{ categoryLabel(r.category) }}<ng-container *ngIf="r.classification?.subcategory"> • {{ subcategoryLabel(r.classification?.subcategory) }}</ng-container></span>
              <span class="status-chip status-location" *ngIf="r.triage_state === 'in_moderation'"><span class="material-symbols-outlined">gavel</span> Em moderação</span>
              <span class="status-chip status-location" *ngIf="r.triage_state === 'rejected'"><span class="material-symbols-outlined">block</span> Rejeitado</span>
            </div>
            <h1>{{ r.description || 'Reporte enviado só com foto' }}</h1>
            <div class="incident-meta">
              <span><span class="material-symbols-outlined">schedule</span> Registrado em {{ formatDateTime(r.received_at) }}</span><i>•</i>
              <span><span class="material-symbols-outlined">group</span> {{ r.confirmation_count }} confirmações de outros cidadãos</span>
              <small *ngIf="r.classification">CLASSIFICAÇÃO: {{ r.classification.source === 'ai' ? 'IA (' + r.classification.model + ')' : r.classification.model === 'moderacao' ? 'MODERAÇÃO' : 'CIDADÃO' }}</small>
            </div>
          </div>
          <aside class="sla-card">
            <div><span class="material-symbols-outlined">timer</span><strong>PRAZO</strong><b>{{ r.status === 'resolvido' ? 'Concluído' : deadlineLabel(r.deadline) }}</b></div>
            <small>{{ r.deadline ? 'Vence em ' + formatDateTime(r.deadline) : 'Prazo definido no encaminhamento' }}</small>
          </aside>
        </section>

        <div class="detail-columns">
          <div class="detail-main-column">
            <section class="content-card evidence-card" *ngIf="r.has_photo">
              <div class="card-title-row"><span class="title-icon green-tint"><span class="material-symbols-outlined">photo_camera</span></span><div><h2>Foto enviada pelo cidadão</h2><p>Metadados removidos no processamento (LGPD)</p></div></div>
              <img *ngIf="r.photo_url; else noPhoto" class="report-photo" [src]="r.photo_url" alt="Foto do reporte" />
              <ng-template #noPhoto><p class="action-intro">A foto ainda está sendo processada.</p></ng-template>
            </section>

            <section class="content-card map-card">
              <div class="card-title-row"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">map</span></span><div><h2>Localização</h2><p>{{ r.lat | number: '1.5-5' }}, {{ r.lon | number: '1.5-5' }}</p></div><a [href]="osmLink(r)" target="_blank" rel="noreferrer">Abrir no mapa <span class="material-symbols-outlined">open_in_new</span></a></div>
              <iframe class="report-map" [src]="mapUrl()" title="Mapa da ocorrência" loading="lazy"></iframe>
            </section>

            <section class="content-card timeline-card">
              <div class="card-title-row"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">timeline</span></span><div><h2>Linha do tempo e trilha de auditoria</h2><p>Eventos gravados no banco; cidadãos aparecem mascarados</p></div><span class="event-count">{{ r.timeline.length }} eventos</span></div>
              <ol class="timeline">
                <li *ngFor="let event of r.timeline; let last = last">
                  <span class="timeline-dot" [class.done]="!last" [class.current]="last"><span class="material-symbols-outlined">{{ last ? 'schedule' : 'check' }}</span></span>
                  <div>
                    <div><strong>{{ eventLabel(event.type) }}</strong><time>{{ formatDateTime(event.created_at) }}</time></div>
                    <p>{{ event.actor }}<ng-container *ngIf="event.justification"> — “{{ event.justification }}”</ng-container></p>
                  </div>
                </li>
              </ol>
            </section>
          </div>

          <aside class="detail-side-column">
            <section class="content-card action-card">
              <div class="card-title-row"><span class="title-icon spotlight-tint"><span class="material-symbols-outlined">bolt</span></span><div><h2>Ações</h2></div></div>
              <p class="action-feedback" role="status" *ngIf="actionMessage()">{{ actionMessage() }}</p>
              <p class="action-feedback error-feedback" role="alert" *ngIf="actionError()">{{ actionError() }}</p>

              <div class="action-panel" *ngIf="canChangeStatus() && r.status !== 'resolvido'">
                <h3><span class="material-symbols-outlined">sync</span> Atualizar status</h3>
                <div class="status-options">
                  <label *ngIf="r.status === 'encaminhado'"><input type="radio" name="action" [(ngModel)]="statusAction" value="in_progress" /><span><i class="status-yellow-dot"></i> Iniciar atendimento</span></label>
                  <label *ngIf="r.status === 'em_andamento'"><input type="radio" name="action" [(ngModel)]="statusAction" value="resolved" /><span><i class="status-green-dot"></i> Resolvido</span></label>
                  <label><input type="radio" name="action" [(ngModel)]="statusAction" value="contest" /><span><i class="status-red-dot"></i> Contestar</span></label>
                </div>
                <label class="field" *ngIf="statusAction === 'in_progress'">Prazo para concluir
                  <input type="datetime-local" [(ngModel)]="statusDeadline" [min]="minDeadline" />
                </label>
                <label class="field" *ngIf="statusAction === 'resolved' || statusAction === 'contest'">Justificativa (vai para o cidadão)
                  <textarea [(ngModel)]="statusJustification" maxlength="1000" rows="3"></textarea>
                </label>
                <button class="button button-green full-button" type="button" [disabled]="busy() || !statusReady()" (click)="submitStatus(r)"><span class="material-symbols-outlined">edit_note</span> Confirmar</button>
              </div>

              <div class="action-panel redirect-panel" *ngIf="canRedirect() && (r.status === 'encaminhado' || r.status === 'em_andamento')">
                <h3><span class="material-symbols-outlined">account_balance</span> Redirecionar a outro órgão</h3>
                <p>Use quando a ocorrência não é da competência do órgão atual.</p>
                <label class="field">Órgão de destino
                  <select [(ngModel)]="redirectAgency">
                    <option value="">Selecione…</option>
                    <option *ngFor="let agency of redirectTargets(r)" [value]="agency.id">{{ agency.name }}</option>
                  </select>
                </label>
                <label class="field">Justificativa
                  <textarea [(ngModel)]="redirectJustification" maxlength="1000" rows="3"></textarea>
                </label>
                <button class="all-agencies" type="button" [disabled]="busy() || !redirectAgency || !redirectJustification.trim()" (click)="submitRedirect(r)"><span class="material-symbols-outlined">swap_horiz</span> Redirecionar</button>
              </div>

              <div class="action-panel" *ngIf="canModerate() && r.triage_state === 'in_moderation'">
                <h3><span class="material-symbols-outlined">gavel</span> Moderação</h3>
                <p>Aprovar mantém o órgão atual ou, com categoria, reclassifica e encaminha. Rejeitar tira o reporte do mapa.</p>
                <label class="field">Categoria (opcional na aprovação)
                  <select [(ngModel)]="moderationCategory">
                    <option value="">Manter a atual</option>
                    <option *ngFor="let option of categories" [value]="option.value">{{ option.label }}</option>
                  </select>
                </label>
                <label class="field" *ngIf="moderationCategory">Subcategoria (opcional, ex.: buraco_via)
                  <input type="text" [(ngModel)]="moderationSubcategory" maxlength="64" />
                </label>
                <label class="field">Justificativa
                  <textarea [(ngModel)]="moderationJustification" maxlength="1000" rows="3"></textarea>
                </label>
                <div class="moderation-buttons">
                  <button class="button button-green" type="button" [disabled]="busy() || !moderationJustification.trim()" (click)="submitModeration(r, 'approve')">Aprovar</button>
                  <button class="button" type="button" [disabled]="busy() || !moderationJustification.trim()" (click)="submitModeration(r, 'reject')">Rejeitar</button>
                </div>
              </div>

              <p class="action-intro" *ngIf="!inScope()">Este reporte agora é de {{ r.agency?.name }}; seu órgão não pode mais alterá-lo.</p>
              <p class="action-intro" *ngIf="inScope() && !hasActions(r)">Nenhuma ação disponível para o seu perfil neste estado.</p>
            </section>

            <section class="content-card owner-card">
              <div class="owner-heading"><span class="eyebrow">ÓRGÃO RESPONSÁVEL</span><span class="custody-pill" *ngIf="r.agency">Em custódia</span></div>
              <div class="owner-info"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">apartment</span></span><div><small>ÓRGÃO</small><strong>{{ r.agency?.name || 'Ainda sem órgão (moderação)' }}</strong><small *ngIf="r.deadline">Prazo: {{ formatDateTime(r.deadline) }}</small></div></div>
            </section>
          </aside>
        </div>
      </ng-container>
    </div>
  `,
  styleUrl: './occurrence-detail.component.css',
})
export class OccurrenceDetailComponent implements OnInit {
  private readonly api = inject(StaffApiService);
  private readonly auth = inject(AuthService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly route = inject(ActivatedRoute);

  readonly statusLabels = STATUS_LABELS;
  readonly categoryLabel = categoryLabel;
  readonly subcategoryLabel = subcategoryLabel;
  readonly formatDateTime = formatDateTime;
  readonly deadlineLabel = deadlineLabel;
  readonly categories = (Object.keys(CATEGORY_LABELS) as ReportCategory[]).map((value) => ({
    value,
    label: CATEGORY_LABELS[value],
  }));
  /** Mínimo de 1h à frente, em hora local (toISOString daria UTC: +3h no Brasil). */
  readonly minDeadline = toDateTimeLocal(new Date(Date.now() + 3_600_000));

  readonly report = signal<ReportDetail | null>(null);
  readonly loadError = signal('');
  readonly actionMessage = signal('');
  readonly actionError = signal('');
  readonly busy = signal(false);
  private readonly agencies = signal<AgencyRef[]>([]);

  private readonly role = computed(() => this.auth.profile()?.role ?? '');
  /** Operador de órgão só age enquanto o reporte é do órgão dele (muda após redirecionar). */
  readonly inScope = computed(() => {
    const own = this.auth.profile()?.agency?.id;
    return this.role() !== 'agency' || (!!own && this.report()?.agency?.id === own);
  });
  readonly canChangeStatus = computed(() => this.role() === 'agency' && this.inScope());
  readonly canRedirect = computed(() => ['agency', 'manager', 'admin'].includes(this.role()) && this.inScope());
  readonly canModerate = computed(() => ['moderator', 'admin'].includes(this.role()));
  readonly mapUrl = computed<SafeResourceUrl | null>(() => {
    const report = this.report();
    if (!report) return null;
    const delta = 0.004;
    const bbox = [report.lon - delta, report.lat - delta, report.lon + delta, report.lat + delta].map((n) => n.toFixed(5)).join(',');
    const url = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${report.lat.toFixed(5)},${report.lon.toFixed(5)}`;
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  });

  statusAction: StatusChange['action'] | '' = '';
  statusDeadline = '';
  statusJustification = '';
  redirectAgency = '';
  redirectJustification = '';
  moderationCategory: ReportCategory | '' = '';
  moderationSubcategory = '';
  moderationJustification = '';

  async ngOnInit(): Promise<void> {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    try {
      this.report.set(await this.api.detail(id));
    } catch (error) {
      this.loadError.set(error instanceof StaffApiError ? error.message : 'Falha ao carregar o reporte.');
      return;
    }
    if (this.canRedirect()) {
      try {
        this.agencies.set(await this.api.redirectTargets());
      } catch {
        this.agencies.set([]);
      }
    }
  }

  urgencyLabel(urgency: string): string {
    return URGENCY_LABELS[urgency] ?? urgency;
  }

  eventLabel(type: string): string {
    return EVENT_LABELS[type] ?? type;
  }

  osmLink(report: ReportDetail): string {
    return `https://www.openstreetmap.org/?mlat=${report.lat}&mlon=${report.lon}#map=18/${report.lat}/${report.lon}`;
  }

  redirectTargets(report: ReportDetail): AgencyRef[] {
    return this.agencies().filter((agency) => agency.id !== report.agency?.id);
  }

  hasActions(report: ReportDetail): boolean {
    const open = report.status === 'encaminhado' || report.status === 'em_andamento';
    return (
      (this.canChangeStatus() && report.status !== 'resolvido') ||
      (this.canRedirect() && open) ||
      (this.canModerate() && report.triage_state === 'in_moderation')
    );
  }

  statusReady(): boolean {
    if (this.statusAction === 'in_progress') return !!this.statusDeadline;
    if (this.statusAction === 'resolved' || this.statusAction === 'contest') return !!this.statusJustification.trim();
    return false;
  }

  async submitStatus(report: ReportDetail): Promise<void> {
    if (!this.statusAction) return;
    const change: StatusChange = { action: this.statusAction };
    if (this.statusAction === 'in_progress') change.deadline = new Date(this.statusDeadline).toISOString();
    else change.justification = this.statusJustification.trim();
    await this.run(() => this.api.changeStatus(report.id, change), 'Status atualizado. O cidadão foi notificado.');
    this.statusAction = '';
    this.statusJustification = '';
  }

  async submitRedirect(report: ReportDetail): Promise<void> {
    const target = this.agencies().find((agency) => agency.id === this.redirectAgency);
    const ok = await this.run(
      () => this.api.redirect(report.id, { agency_id: this.redirectAgency, justification: this.redirectJustification.trim() }),
      `Reporte redirecionado para ${target?.name ?? 'o novo órgão'}.`,
    );
    if (ok) {
      this.redirectAgency = '';
      this.redirectJustification = '';
    }
  }

  async submitModeration(report: ReportDetail, decision: 'approve' | 'reject'): Promise<void> {
    const request = {
      justification: this.moderationJustification.trim(),
      ...(decision === 'approve' && this.moderationCategory
        ? { category: this.moderationCategory, subcategory: this.moderationSubcategory.trim() || undefined }
        : {}),
    };
    const ok = await this.run(
      () => this.api.moderate(report.id, decision, request),
      decision === 'approve' ? 'Reporte aprovado.' : 'Reporte rejeitado e retirado do mapa.',
    );
    if (ok) this.moderationJustification = '';
  }

  /** Executa a ação; a resposta é o detalhe atualizado (pode sair do escopo). */
  private async run(action: () => Promise<ReportDetail>, success: string): Promise<boolean> {
    this.busy.set(true);
    this.actionError.set('');
    this.actionMessage.set('');
    try {
      this.report.set(await action());
      this.actionMessage.set(success);
      return true;
    } catch (error) {
      this.actionError.set(error instanceof StaffApiError ? error.message : 'Não foi possível concluir a ação.');
      return false;
    } finally {
      this.busy.set(false);
    }
  }
}
