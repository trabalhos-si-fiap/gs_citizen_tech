import { Component, OnDestroy, inject } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ROLE_LABELS } from './auth.models';
import { AuthService } from './auth.service';

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
            <span class="nav-count">12</span>
          </a>
          <a routerLink="/dashboard" fragment="mapa" title="Mapa de Operações">
            <span class="material-symbols-outlined" aria-hidden="true">map</span> Mapa de Operações
          </a>
          <a routerLink="/dashboard" fragment="equipes" title="Equipes & Frotas">
            <span class="material-symbols-outlined" aria-hidden="true">local_shipping</span> Equipes &amp; Frotas
            <span class="nav-soon">Em Breve</span>
          </a>
          <a routerLink="/indicadores" routerLinkActive="active" title="Indicadores Públicos">
            <span class="material-symbols-outlined" aria-hidden="true">analytics</span> Relatórios
          </a>
          <a routerLink="/dashboard" fragment="configuracoes" title="Configurações da Secretaria">
            <span class="material-symbols-outlined" aria-hidden="true">tune</span> Configurações da Secretaria
          </a>
        </nav>

        <div class="sidebar-bottom">
          <div class="sla-summary">
            <span class="material-symbols-outlined" aria-hidden="true">verified</span>
            <span><small>SLA Diário</small><strong>94.2% Concluído</strong></span>
            <span class="material-symbols-outlined arrow" aria-hidden="true">chevron_right</span>
          </div>
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
          <div class="shift-pill" [class.dashboard-hidden]="isDashboard"><i></i><span>Expediente Ordinário:<strong>08:00 – 18:00</strong></span></div>
          <button class="icon-button notification-button" type="button" aria-label="Notificações">
            <span class="material-symbols-outlined" aria-hidden="true">notifications</span><b>3</b>
          </button>
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
export class ShellComponent implements OnDestroy {
  readonly auth = inject(AuthService);
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

  ngOnDestroy(): void {
    this.navigationSubscription.unsubscribe();
  }
}
