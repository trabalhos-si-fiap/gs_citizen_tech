import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-occurrence-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="detail-page">
      <div class="detail-toolbar">
        <div class="breadcrumbs">
          <a routerLink="/ocorrencias"><span class="material-symbols-outlined">arrow_back</span> Voltar à Lista</a>
          <span>/</span><span>Gestão de Reportes</span><span>/</span><strong>#{{ protocol }}</strong>
        </div>
        <div class="toolbar-actions"><span class="official-pill"><i></i> Canal Oficial Aberto</span><button class="icon-button" type="button" aria-label="Imprimir" (click)="showPrintNotice = true"><span class="material-symbols-outlined">print</span></button><button class="icon-button" type="button" aria-label="Compartilhar"><span class="material-symbols-outlined">share</span></button></div>
      </div>
      <p class="feedback-message" role="status" *ngIf="showPrintNotice">Impressão de relatório disponível após a integração com o serviço documental.</p>

      <section class="incident-hero">
        <div class="incident-main">
          <div class="incident-tags"><span class="status-chip status-analysis"><i></i> {{ status }}</span><span class="status-chip status-priority"><span class="material-symbols-outlined">warning</span> Prioridade Alta</span><span class="status-chip status-category"><span class="material-symbols-outlined">alt_route</span> Asfalto &amp; Vias Públicas</span><span class="status-chip status-location"><span class="material-symbols-outlined">location_on</span> Zona Sul / Pinheiros</span></div>
          <h1>Cratera profunda com risco iminente de acidente na pista central</h1>
          <div class="incident-meta"><span><span class="material-symbols-outlined">schedule</span> Registrado em 12 de Outubro de 2026 às 08:34 (Há 2 horas)</span><i>•</i><span class="verified-citizen"><span class="material-symbols-outlined">verified_user</span> Munícipe Autenticado (CPF e Gov.br Validados)</span><small>ORIGEM: APP RECLAME JÁ (v3.4.1)</small></div>
        </div>
        <aside class="sla-card"><div><span class="material-symbols-outlined">timer</span><strong>CONTROLE DE SLA</strong><b>70h Restantes</b></div><div class="sla-track"><i></i></div><small>Decorrido: 02h / 72h <strong>Dentro do Prazo Regulamentar</strong></small></aside>
      </section>

      <div class="detail-columns">
        <div class="detail-main-column">
          <section class="content-card evidence-card">
            <div class="card-title-row"><span class="title-icon green-tint"><span class="material-symbols-outlined">photo_camera</span></span><div><h2>Evidências Fotográficas e Ambientais</h2><p>Registradas pelo cidadão no momento do envio com validação EXIF</p></div><span class="attachment-count">2 ANEXOS<br />DIGITAIS</span></div>
            <div class="incident-photo">
              <span class="gps-tag"><span class="material-symbols-outlined">my_location</span> GPS VERIFICADO: -23.578491, -46.689230</span>
              <span class="photo-search material-symbols-outlined">zoom_in</span>
              <div><small>ENDEREÇO DETECTADO POR SATÉLITE</small><strong>Av. Brigadeiro Faria Lima, 2232 (Faixa Central)</strong><span class="geo-badge"><span class="material-symbols-outlined">location_on</span> Georreferenciada</span></div>
            </div>
            <div class="evidence-thumbnails"><span class="mini-photo photo-one"><small>FOTO 01</small></span><span class="mini-photo photo-two"><small>FOTO 02</small></span><button type="button"><span class="material-symbols-outlined">add_a_photo</span>Anexar Vistoria</button><button type="button"><span class="material-symbols-outlined">attach_file</span>Documentos</button></div>
          </section>

          <section class="content-card citizen-report">
            <div class="card-title-row"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">record_voice_over</span></span><div><h2>Depoimento e Relato do Munícipe</h2><p>Declaração prestada via protocolo de solicitação pública</p></div></div>
            <blockquote>“Buraco com cerca de 1 metro de diâmetro na faixa do meio, começou pequeno na chuva de ontem e hoje abriu mais ainda. Quase causou acidente gravíssimo com um motociclista por volta das 08h15. Risco altíssimo com chuva forte prevista para a tarde.”</blockquote>
            <div class="severity-row"><span><span class="material-symbols-outlined">error</span><span><small>NÍVEL DE GRAVIDADE</small><strong>Gravidade Crítica</strong></span></span><span class="status-chip status-priority"><span class="material-symbols-outlined">warning</span> Pista Rápida</span></div>
          </section>

          <section class="content-card map-card">
            <div class="card-title-row"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">map</span></span><div><h2>Localização Cartográfica Oficial</h2><p>Delimitação de malha viária e jurisdição subprefeitural</p></div><a href="https://maps.google.com/?q=-23.578491,-46.689230" target="_blank" rel="noreferrer">Abrir no SIG Municipal <span class="material-symbols-outlined">open_in_new</span></a></div>
            <div class="official-map" role="img" aria-label="Mapa ilustrativo da região de Pinheiros, São Paulo"><span class="map-waterway"></span><span class="map-road road-a"></span><span class="map-road road-b"></span><span class="map-road road-c"></span><span class="map-city">Pinheiros<br /><small>São Paulo</small></span><span class="map-pin material-symbols-outlined">location_on</span><span class="map-address"><span class="material-symbols-outlined">verified</span> Av. Brig. Faria Lima, 2232 <small>Subprefeitura de Pinheiros • Setor 04</small></span></div>
          </section>

          <section class="content-card timeline-card">
            <div class="card-title-row"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">timeline</span></span><div><h2>Linha do Tempo e Trilha de Auditoria</h2><p>Registro inviolável em banco de dados da municipalidade</p></div><span class="event-count">3 Eventos</span></div>
            <ol class="timeline">
              <li><span class="timeline-dot done"><span class="material-symbols-outlined">check</span></span><div><div><strong>Chamado protocolado com sucesso</strong><time>08:34</time></div><p>Munícipe autenticado registrou ocorrência geolocalizada via aplicativo cidadão Reclame Já.</p></div></li>
              <li><span class="timeline-dot done"><span class="material-symbols-outlined">check</span></span><div><div><strong>Triagem automática e catalogação inteligente</strong><time>09:15</time></div><p>Sistema identificou malha viária crítica e atribuiu protocolo oficial <b>#{{ protocol }}</b>.</p></div></li>
              <li><span class="timeline-dot current"><span class="material-symbols-outlined">schedule</span></span><div><div><strong>Encaminhado à Secretaria de Infraestrutura Urbana</strong><time>09:40 (Atual)</time></div><p>Alocado no Departamento de Conservação Viária sob responsabilidade do fiscal Eng. Roberto Silveira.</p></div></li>
            </ol>
          </section>
        </div>

        <aside class="detail-side-column">
          <section class="content-card action-card">
            <div class="card-title-row"><span class="title-icon spotlight-tint"><span class="material-symbols-outlined">bolt</span></span><div><h2>Ações Imediatas da Ocorrência</h2></div><i class="live-dot"></i></div>
            <p class="action-intro">Selecione a resolução administrativa para atualizar a malha operacional da prefeitura.</p>
            <div class="action-panel" *ngIf="canChangeStatus">
              <h3><span class="material-symbols-outlined">sync</span> Atualizar Status do Processo</h3>
              <p>Altera o ciclo de vida da demanda e notifica os canais centrais.</p>
              <div class="status-options">
                <label><input type="radio" name="status" [(ngModel)]="pendingStatus" value="Em Análise Técnica" /><span><i class="status-blue-dot"></i> Em Análise</span></label>
                <label><input type="radio" name="status" [(ngModel)]="pendingStatus" value="Em Execução" /><span><i class="status-yellow-dot"></i> Em Execução</span></label>
                <label><input type="radio" name="status" [(ngModel)]="pendingStatus" value="Resolvido" /><span><i class="status-green-dot"></i> Resolvido</span></label>
                <label><input type="radio" name="status" [(ngModel)]="pendingStatus" value="Indeferido" /><span><i class="status-red-dot"></i> Indeferido</span></label>
              </div>
              <button class="button button-green full-button" type="button" (click)="confirmStatus()"><span class="material-symbols-outlined">edit_note</span> Confirmar Alteração de Status</button>
              <p class="action-feedback" role="status" *ngIf="statusMessage">{{ statusMessage }}</p>
            </div>

            <div class="action-panel redirect-panel">
              <h3><span class="material-symbols-outlined">account_balance</span> Direcionar a Outro Órgão <a href="#orgaos">1 Clique</a></h3>
              <p>A ocorrência não é de competência desta secretaria? Transfira de imediato:</p>
              <div class="agency-options"><button type="button" (click)="routeMessage = 'CET / Trânsito'"><span class="material-symbols-outlined">traffic</span> CET / Trânsito</button><button type="button" (click)="routeMessage = 'Iluminação Pública'"><span class="material-symbols-outlined">lightbulb</span> Iluminação Pública</button><button type="button" (click)="routeMessage = 'SABESP / Água'"><span class="material-symbols-outlined">water_drop</span> SABESP / Água</button><button type="button" (click)="routeMessage = 'Limpeza Urbana'"><span class="material-symbols-outlined">delete_sweep</span> Limpeza Urbana</button></div>
              <button class="all-agencies" id="orgaos" type="button" (click)="routeMessage = 'A lista completa de órgãos estará disponível após a integração.'"><span class="material-symbols-outlined">swap_horiz</span> Ver Todos os 18 Órgãos Municipais</button>
              <p class="action-feedback" role="status" *ngIf="routeMessage">{{ routeMessage }} selecionado. O encaminhamento requer integração com o serviço de protocolo.</p>
            </div>
          </section>

          <section class="content-card communication-card">
            <div class="card-title-row"><span class="title-icon green-tint"><span class="material-symbols-outlined">send</span></span><div><h2>Comunicação Oficial ao Cidadão</h2><p>Notificação síncrona via App Push, SMS e E-mail</p></div></div>
            <div class="notice-banner"><span class="material-symbols-outlined">campaign</span> As mensagens enviadas aqui aparecem em tempo real no histórico do munícipe.</div>
            <span class="eyebrow quick-label">MODELOS RÁPIDOS PRÉ-APROVADOS:</span>
            <div class="quick-replies"><button type="button" (click)="messageDraft = 'Vistoria agendada para a sua ocorrência.'">+ Vistoria agendada</button><button type="button" (click)="messageDraft = 'A equipe já está em execução no local.'">+ Em execução no local</button><button type="button" (click)="messageDraft = 'Aguardando peças ou materiais para continuidade do serviço.'">+ Aguardando peças/massa</button><button type="button" (click)="messageDraft = 'Serviço concluído. Agradecemos por contribuir com a cidade.'">+ Serviço concluído</button></div>
            <label class="sr-only" for="citizen-message">Atualização para o cidadão</label>
            <textarea id="citizen-message" [(ngModel)]="messageDraft" maxlength="400" placeholder="Digite a atualização para o cidadão (ex: Equipe técnica da 3ª regional destacada para vistoria no local até as 14h...)"></textarea>
            <div class="message-meta"><span><span class="material-symbols-outlined">notifications_active</span> Dispara push notification imediata</span><span>{{ messageDraft.length }} / 400 caracteres</span></div>
            <button class="button button-spotlight full-button" type="button" [disabled]="!messageDraft.trim()" (click)="publishMessage()"><span class="material-symbols-outlined">send</span> Publicar Atualização ao Cidadão</button>
            <p class="action-feedback" role="status" *ngIf="messageStatus">{{ messageStatus }}</p>
          </section>

          <section class="content-card owner-card">
            <div class="owner-heading"><span class="eyebrow">ÓRGÃO E RESPONSÁVEL ATUAL</span><span class="custody-pill">Em Custódia</span></div>
            <div class="owner-info"><span class="title-icon neutral-tint"><span class="material-symbols-outlined">apartment</span></span><div><small>ÓRGÃO CENTRAL</small><strong>Sec. Municipal de Obras e Infraestrutura Urbana (SMOI)</strong><small>Departamento de Conservação Viária (DCV-03)</small></div></div>
            <div class="owner-contact"><span class="owner-initials">RS</span><span><strong>Roberto Silveira</strong><small>Fiscal de Posturas • Matrícula #98124</small></span><button type="button" (click)="contactMessage = 'O contato interno estará disponível após integração com o diretório municipal.'"><span class="material-symbols-outlined">chat</span> Contato Interno</button></div>
            <p class="action-feedback" role="status" *ngIf="contactMessage">{{ contactMessage }}</p>
          </section>
        </aside>
      </div>
      <p class="demo-caption">Protótipo operacional • Alterações de status, encaminhamentos e mensagens ainda não são persistidos.</p>
    </div>
  `,
  styleUrl: './occurrence-detail.component.css',
})
export class OccurrenceDetailComponent {
  private readonly auth = inject(AuthService);
  readonly canChangeStatus = this.auth.profile()?.role === 'agency';
  readonly protocol: string;
  status = 'Em Análise Técnica';
  pendingStatus = this.status;
  statusMessage = '';
  messageDraft = '';
  messageStatus = '';
  routeMessage = '';
  contactMessage = '';
  showPrintNotice = false;

  constructor(route: ActivatedRoute) {
    this.protocol = route.snapshot.paramMap.get('id') ?? 'REC-2024-8921';
  }

  confirmStatus(): void {
    this.status = this.pendingStatus;
    this.statusMessage = `Status demonstrativo alterado para “${this.status}”. A mudança não foi salva no servidor.`;
  }

  publishMessage(): void {
    if (!this.messageDraft.trim()) return;
    this.messageStatus = 'Mensagem preparada em modo de demonstração; não foi enviada ao cidadão.';
  }
}
