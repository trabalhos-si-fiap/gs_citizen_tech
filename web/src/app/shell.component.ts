import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ROLE_LABELS } from './auth.models';
import { AuthService } from './auth.service';
import { StaffApiService } from './staff-api.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="app-shell">
      <aside class="sidebar" aria-label="Navegação principal">
        <a class="brand-lockup" routerLink="/dashboard" aria-label="Reclame Já, página inicial">
          <span class="brand-mark material-symbols-outlined" aria-hidden="true">domain</span>
          <span class="brand-copy"><strong>Reclame Já</strong><small>GESTÃO PÚBLICA</small></span>
        </a>

        <section class="jurisdiction">
          <span class="eyebrow">JURISDIÇÃO ATIVA</span>
          <strong>{{ agencyName }}</strong>
          <span class="online"><i></i> Servidor Oficial Ativo</span>
        </section>

        <nav class="primary-nav">
          <a routerLink="/dashboard" routerLinkActive="active" title="Visão Geral">
            <span class="material-symbols-outlined" aria-hidden="true">grid_view</span> Visão Geral
          </a>
          <a routerLink="/ocorrencias" routerLinkActive="active" title="Gestão de Ocorrências">
            <span class="material-symbols-outlined" aria-hidden="true">warning</span> Gestão de Ocorrências
            @if (waiting() !== null) {
              <span class="nav-count" title="Aguardando atendimento">{{ waiting() }}</span>
            }
          </a>
          @if (canModerate) {
            <a routerLink="/moderacao" routerLinkActive="active" title="Fila de moderação">
              <span class="material-symbols-outlined" aria-hidden="true">gavel</span> Moderação
            </a>
          }
          <a routerLink="/dashboard" fragment="regioes" title="Regiões com mais reportes">
            <span class="material-symbols-outlined" aria-hidden="true">map</span> Regiões
          </a>
          <a routerLink="/indicadores" routerLinkActive="active" title="Indicadores Públicos">
            <span class="material-symbols-outlined" aria-hidden="true">analytics</span> Indicadores públicos
          </a>
        </nav>

        <div class="sidebar-bottom">
          @if (overdue() !== null) {
            <a class="sla-summary" routerLink="/ocorrencias" title="Reportes com prazo vencido">
              <span class="material-symbols-outlined" aria-hidden="true">{{ overdue() ? 'warning' : 'verified' }}</span>
              <span><small>Prazos vencidos</small><strong>{{ overdue() }} {{ overdue() === 1 ? 'reporte' : 'reportes' }}</strong></span>
              <span class="material-symbols-outlined arrow" aria-hidden="true">chevron_right</span>
            </a>
          }
          <button class="logout-link" type="button" (click)="auth.logout()">
            <span class="material-symbols-outlined" aria-hidden="true">logout</span> Encerrar Expediente
          </button>
        </div>
      </aside>

      <div class="workspace">
        <header class="topbar" [class.dashboard-topbar]="isDashboard">
          <div class="secretary-select">
            <span class="material-symbols-outlined" aria-hidden="true">account_balance</span>
            <span><small>Secretaria Ativa</small><strong>{{ agencyName }}</strong></span>
            <span class="material-symbols-outlined" aria-hidden="true">expand_more</span>
          </div>
          <div class="topbar-spacer"></div>
          <div class="profile">
            <span class="profile-identity" [class.dashboard-hidden]="isDashboard"><strong>{{ auth.profile()?.email }}</strong><small>{{ roleLabel }}</small></span>
            <span class="avatar material-symbols-outlined" aria-hidden="true">person</span>
          </div>
        </header>
        <main class="page-content"><router-outlet /></main>
      </div>
    </div>
  `,
  styleUrl: './shell.component.css',
})
export class ShellComponent implements OnInit, OnDestroy {
  readonly auth = inject(AuthService);
  private readonly api = inject(StaffApiService);
  readonly waiting = signal<number | null>(null);
  readonly overdue = signal<number | null>(null);
  private readonly router = inject(Router);
  private readonly navigationSubscription = this.router.events.subscribe((event) => {
    if (event instanceof NavigationEnd) {
      this.isDashboard = event.urlAfterRedirects === '/dashboard' || event.urlAfterRedirects.startsWith('/dashboard#');
    }
  });

  isDashboard = this.router.url === '/dashboard' || this.router.url.startsWith('/dashboard#');

  get agencyName(): string {
    const profile = this.auth.profile();
    return profile?.agency?.name ?? (profile?.scope === 'all' ? 'Todos os órgãos' : 'Prefeitura Municipal');
  }

  get roleLabel(): string {
    const role = this.auth.profile()?.role ?? '';
    return (ROLE_LABELS[role] ?? role).toUpperCase();
  }

  get canModerate(): boolean {
    return ['moderator', 'admin'].includes(this.auth.profile()?.role ?? '');
  }

  async ngOnInit(): Promise<void> {
    try {
      const summary = await this.api.summary();
      this.waiting.set(summary.by_status.encaminhado);
      this.overdue.set(summary.overdue);
    } catch {
      // Contadores são complementares; as telas mostram os erros.
    }
  }

  ngOnDestroy(): void {
    this.navigationSubscription.unsubscribe();
  }
}
