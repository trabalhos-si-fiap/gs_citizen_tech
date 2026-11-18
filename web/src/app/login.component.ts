import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

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

          <form (ngSubmit)="submitLogin()">
            <div class="field-group">
              <label for="department"><span class="material-symbols-outlined" aria-hidden="true">domain</span> Órgão / Secretaria Solicitante <small>obrigatório</small></label>
              <div class="select-wrap">
                <select id="department" name="department" [(ngModel)]="department" required>
                  <option value="siurb">SIURB • Sec. Mun. de Infraestrutura Urbana</option>
                  <option value="smt">SMT • Sec. de Mobilidade e Trânsito</option>
                  <option value="ilume">ILUME • Dep. Iluminação Pública</option>
                  <option value="amlurb">AMLURB • Limpeza Urbana e Resíduos</option>
                  <option value="smsu">SMSU • Sec. Mun. de Segurança Urbana</option>
                  <option value="smsp">SMSP • Sec. Mun. das Subprefeituras</option>
                </select>
                <span class="material-symbols-outlined" aria-hidden="true">expand_more</span>
              </div>
            </div>

            <div class="field-group">
              <label for="identity"><span class="material-symbols-outlined" aria-hidden="true">mail</span> E-mail Institucional <small>&#64;prefeitura.gov.br</small></label>
              <div class="input-wrap">
                <input id="identity" name="identity" type="email" [(ngModel)]="identity" autocomplete="username" placeholder="servidor&#64;prefeitura.gov.br" required />
              </div>
            </div>

            <div class="field-group">
              <div class="label-row">
                <label for="password"><span class="material-symbols-outlined" aria-hidden="true">lock</span> Senha de Acesso</label>
                <button class="text-button" type="button" (click)="showHelp = !showHelp">Esqueceu a senha?</button>
              </div>
              <div class="input-wrap">
                <input id="password" name="password" [(ngModel)]="password" [type]="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="••••••••••••" required />
                <button class="password-toggle material-symbols-outlined" type="button" (click)="showPassword = !showPassword" [attr.aria-label]="showPassword ? 'Ocultar senha' : 'Mostrar senha'">{{ showPassword ? 'visibility_off' : 'visibility' }}</button>
              </div>
            </div>

            <div class="remember-row">
              <label class="checkbox-label"><input type="checkbox" name="remember" [(ngModel)]="rememberStation" /> Manter conectado neste dispositivo</label>
              <span class="secure-session"><span class="material-symbols-outlined" aria-hidden="true">shield</span> Sessão Segura</span>
            </div>
            <p class="login-message" role="status" *ngIf="message">{{ message }}</p>
            <p class="login-message help-message" role="status" *ngIf="showHelp">Para primeiro acesso ou redefinição de senha, contate o suporte institucional da sua secretaria.</p>
            <button class="primary-login-button" type="submit">
              Entrar no Sistema <span class="material-symbols-outlined" aria-hidden="true">login</span>
            </button>
            <div class="support-link"><button type="button" (click)="showHelp = !showHelp"><span class="material-symbols-outlined" aria-hidden="true">help_outline</span> Primeiro acesso ou suporte institucional</button></div>
          </form>

          <div class="login-footer">
            <span><span class="material-symbols-outlined" aria-hidden="true">lock</span> Ambiente seguro • Prefeitura Municipal</span>
            <span>© 2024 Zeladoria Urbana</span>
          </div>
          <p class="prototype-note">Protótipo: autenticação institucional ainda não conectada ao serviço de identidade.</p>
        </section>
      </div>
    </main>
  `,
  styleUrl: './login.component.css',
})
export class LoginComponent {
  department = 'siurb';
  identity = '';
  password = '';
  rememberStation = true;
  showPassword = false;
  showHelp = false;
  message = '';

  submitLogin(): void {
    this.message = 'A autenticação institucional ainda não está conectada. Nenhuma credencial foi enviada.';
  }
}
