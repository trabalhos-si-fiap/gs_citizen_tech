import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthError, AuthErrorKind } from './auth.models';
import { AuthService } from './auth.service';

const ERROR_MESSAGES: Record<AuthErrorKind, string> = {
  consent: 'Este e-mail não está habilitado como servidor. Contate o suporte da sua secretaria.',
  invalid_code: 'Código inválido, expirado ou bloqueado. Solicite um novo código.',
  forbidden: 'Esta conta não tem permissão de servidor ou não possui órgão vinculado.',
  unavailable: 'Serviço indisponível. Tente novamente em instantes.',
  network: 'Não foi possível conectar à API.',
  unknown: 'Não foi possível concluir a operação. Tente novamente.',
};

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <main class="login-page">
      <div class="login-layout">
        <section class="login-intro">
          <a class="login-brand" routerLink="/login">
            <span class="brand-mark material-symbols-outlined" aria-hidden="true">assured_workload</span>
            <span><small>PORTAL GOVERNAMENTAL</small><strong>Zeladoria Integrada</strong></span>
          </a>
          <div class="intro-copy">
            <h1>Gestão Urbana em Tempo Real</h1>
            <p>Acompanhamento centralizado e despacho integrado de serviços públicos urbanos.</p>
          </div>
          <div class="intro-metrics">
            <div class="metric-heading"><span class="eyebrow">DEMANDAS DE HOJE</span><span class="live-pill"><i></i> Ao Vivo</span></div>
            <div class="metric-values"><div><strong>1.482</strong><span>Chamados em Triagem</span></div><div><strong>94,6%</strong><span>SLA Atendido</span></div></div>
          </div>
          <div class="security-note">
            <span class="material-symbols-outlined" aria-hidden="true">verified_user</span>
            <div>
              <strong>Acesso Institucional Seguro</strong>
              <small>Sistema Oficial de Zeladoria e Serviços Urbanos</small>
            </div>
          </div>
        </section>

        <section class="login-card">
          <div class="login-card-heading">
            <div class="municipal-brand">
              <span class="material-symbols-outlined" aria-hidden="true">location_city</span>
              <span><small>PREFEITURA MUNICIPAL</small><strong>Reclame Já - Servidor</strong></span>
            </div>
          </div>
          <div class="login-card-title">
            <h2>Autenticação Institucional</h2>
            <p class="form-intro">Acesso seguro para servidores, gestores e equipes operacionais municipais.</p>
          </div>

          <form (ngSubmit)="submit()">
            <div class="field-group">
              <label for="identity"><span class="material-symbols-outlined" aria-hidden="true">mail</span> E-mail Institucional</label>
              <div class="input-wrap">
                <input id="identity" name="identity" type="email" [(ngModel)]="email" [readonly]="step() === 'code'" autocomplete="username" placeholder="servidor&#64;prefeitura.gov.br" required />
              </div>
            </div>

            <div class="field-group" *ngIf="step() === 'code'">
              <div class="label-row">
                <label for="code"><span class="material-symbols-outlined" aria-hidden="true">pin</span> Código de 6 dígitos</label>
                <button class="text-button" type="button" (click)="resend()" [disabled]="loading() || resendCooldown() > 0">{{ resendCooldown() > 0 ? 'Reenviar código (' + resendCooldown() + 's)' : 'Reenviar código' }}</button>
              </div>
              <div class="input-wrap">
                <input id="code" name="code" type="text" inputmode="numeric" maxlength="6" pattern="[0-9]{6}" [(ngModel)]="code" autocomplete="one-time-code" placeholder="000000" required />
              </div>
            </div>

            <div class="remember-row">
              <label class="checkbox-label"><input type="checkbox" name="remember" [(ngModel)]="rememberStation" /> Manter conectado neste dispositivo</label>
              <span class="secure-session"><span class="material-symbols-outlined" aria-hidden="true">shield</span> Sessão Segura</span>
            </div>
            <p class="login-message" role="alert" *ngIf="message()">{{ message() }}</p>
            <button class="primary-login-button" type="submit" [disabled]="loading()">
              {{ step() === 'email' ? 'Enviar código' : 'Entrar no Sistema' }} <span class="material-symbols-outlined" aria-hidden="true">login</span>
            </button>
            <div class="support-link">
              <button type="button" *ngIf="step() === 'code'" (click)="changeEmail()"><span class="material-symbols-outlined" aria-hidden="true">arrow_back</span> Usar outro e-mail</button>
              <button type="button" (click)="showHelp = !showHelp"><span class="material-symbols-outlined" aria-hidden="true">help_outline</span> Suporte institucional</button>
            </div>
            <p class="login-message help-message" role="status" *ngIf="showHelp">Para primeiro acesso ou problemas de permissão, contate o suporte institucional da sua secretaria.</p>
          </form>

          <div class="login-footer">
            <span><span class="material-symbols-outlined" aria-hidden="true">lock</span> Ambiente seguro • Prefeitura Municipal</span>
            <span>© 2024 Zeladoria Urbana</span>
          </div>
        </section>
      </div>
    </main>
  `,
  styleUrl: './login.component.css',
})
export class LoginComponent implements OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private cooldownTimer: ReturnType<typeof setInterval> | undefined;

  readonly step = signal<'email' | 'code'>('email');
  email = '';
  code = '';
  rememberStation = true;
  showHelp = false;
  readonly loading = signal(false);
  readonly message = signal('');
  readonly resendCooldown = signal(0);

  async submit(): Promise<void> {
    if (this.loading()) return;
    this.message.set('');
    this.loading.set(true);
    try {
      if (this.step() === 'email') {
        await this.auth.requestCode(this.email.trim());
        this.step.set('code');
        this.startCooldown();
      } else {
        await this.auth.verifyCode(this.email.trim(), this.code.trim(), this.rememberStation);
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
        await this.router.navigateByUrl(returnUrl?.startsWith('/') && !returnUrl.startsWith('//') ? returnUrl : '/dashboard');
      }
    } catch (error) {
      this.message.set(ERROR_MESSAGES[error instanceof AuthError ? error.kind : 'unknown']);
    } finally {
      this.loading.set(false);
    }
  }

  async resend(): Promise<void> {
    if (this.loading() || this.resendCooldown() > 0) return;
    this.message.set('');
    this.loading.set(true);
    try {
      await this.auth.requestCode(this.email.trim());
      this.code = '';
      this.startCooldown();
    } catch (error) {
      this.message.set(ERROR_MESSAGES[error instanceof AuthError ? error.kind : 'unknown']);
    } finally {
      this.loading.set(false);
    }
  }

  changeEmail(): void {
    this.step.set('email');
    this.code = '';
    this.message.set('');
  }

  ngOnDestroy(): void {
    clearInterval(this.cooldownTimer);
  }

  private startCooldown(): void {
    clearInterval(this.cooldownTimer);
    this.resendCooldown.set(30);
    this.cooldownTimer = setInterval(() => {
      this.resendCooldown.update((value) => value - 1);
      if (this.resendCooldown() <= 0) clearInterval(this.cooldownTimer);
    }, 1000);
  }
}
