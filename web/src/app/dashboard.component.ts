import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="dashboard-page">
      <div class="dashboard-heading">
        <div>
          <h1>Painel de Controle de Zeladoria</h1>
          <p>Monitoramento consolidado de intervenções viárias, ordens de serviço e despacho emergencial da SMISU.</p>
        </div>
        <div class="heading-actions">
          <div class="date-tabs" aria-label="Período do painel"><button class="selected" type="button">Hoje</button><button type="button">Últimos 7 dias</button><button type="button">Mês Atual</button></div>
          <button type="button" class="button button-spotlight" (click)="exportNotice = true"><span class="material-symbols-outlined" aria-hidden="true">download</span> Exportar Relatório Diário</button>
        </div>
      </div>
      <p class="export-notice" role="status" *ngIf="exportNotice">Exportação demonstrativa: conecte o serviço de relatórios para gerar um arquivo.</p>

      <section class="summary-grid" aria-label="Indicadores operacionais">
        <article class="summary-card demand-card">
          <div class="summary-icon yellow-icon"><span class="material-symbols-outlined">pending_actions</span></div>
          <span class="eyebrow">DEMANDAS ATIVAS</span><strong>1.482</strong>
          <div class="summary-foot"><span class="trend new">↗ +8 novas</span><small>nos últimos 30min</small></div>
        </article>
        <article class="summary-card attendance-card">
          <div class="summary-icon blue-icon"><span class="material-symbols-outlined">local_shipping</span></div>
          <span class="eyebrow">EM ATENDIMENTO</span><strong>312</strong>
          <div class="summary-foot"><span class="trend neutral"><span class="material-symbols-outlined">schedule</span> Atendimento Ativo</span><small>chamados em execução</small></div>
        </article>
        <article class="summary-card critical-card">
          <div class="summary-icon red-icon"><span class="material-symbols-outlined">warning</span></div>
          <span class="eyebrow">ALERTAS CRÍTICOS</span><strong class="critical-text">18</strong>
          <div class="summary-foot"><span class="trend alert">Prioritário</span><small>Intervenção prioritária imediata</small></div>
        </article>
        <article class="summary-card resolution-card">
          <div class="summary-icon green-icon"><span class="material-symbols-outlined">task_alt</span></div>
          <span class="eyebrow">SLA RESOLVIDO</span><strong class="green-text">94.6%</strong>
          <div class="summary-foot"><span class="trend good"><span class="material-symbols-outlined">verified</span> Meta batida</span><small>1.038 chamados no prazo pactuado</small></div>
        </article>
      </section>

      <div class="dashboard-columns">
        <section class="chart-card" aria-labelledby="flow-title">
          <div class="card-heading">
            <div><h2 id="flow-title">Fluxo Operacional: Aberturas vs. Conclusões</h2><p>Comparativo diário dos últimos 7 dias úteis em todas as 32 subprefeituras</p></div>
            <div class="chart-legend"><span><i class="legend-yellow"></i>Novos Reportes</span><span><i class="legend-green"></i>Resolvidos / Baixas</span></div>
          </div>
          <div class="chart-area" role="img" aria-label="Gráfico demonstrativo de aberturas e conclusões de ocorrências durante os últimos sete dias">
            <div class="chart-grid"><span></span><span></span><span></span><span></span></div>
            <svg viewBox="0 0 760 240" preserveAspectRatio="none" aria-hidden="true">
              <defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#ebe100" stop-opacity=".42" /><stop offset="100%" stop-color="#ebe100" stop-opacity="0" /></linearGradient></defs>
              <path class="area-path" d="M24 173 L128 130 L230 148 L332 94 L435 117 L538 63 L640 84 L736 42 L736 210 L24 210 Z" />
              <path class="line-report" d="M24 173 L128 130 L230 148 L332 94 L435 117 L538 63 L640 84 L736 42" />
              <path class="line-resolution" d="M24 190 L128 150 L230 129 L332 113 L435 99 L538 62 L640 50 L736 38" />
              <g class="chart-dots"><circle cx="24" cy="173" r="4" /><circle cx="128" cy="130" r="4" /><circle cx="230" cy="148" r="4" /><circle cx="332" cy="94" r="4" /><circle cx="435" cy="117" r="4" /><circle cx="538" cy="63" r="4" /><circle cx="640" cy="84" r="4" /><circle cx="736" cy="42" r="5" /></g>
            </svg>
          </div>
          <div class="chart-days"><span>Seg (18)</span><span>Ter (19)</span><span>Qua (20)</span><span>Qui (21)</span><span>Sex (22)</span><span>Sáb (23)</span><span>Dom (24)</span><strong>Hoje (25)</strong></div>
          <div class="chart-callout"><span class="material-symbols-outlined">trending_up</span><span>A capacidade de resposta atingiu <strong>108%</strong> nas últimas 48h com suporte de mutirões noturnos.<small>SALDO POSITIVO: +142 BAIXAS</small></span></div>
        </section>

        <aside class="alerts-card" aria-labelledby="alerts-title">
          <div class="section-title"><i></i><h2 id="alerts-title">Alertas Imediatos</h2><span class="count-pill">4 Urgentes</span></div>
          <a class="alert-item" routerLink="/ocorrencias/REC-2024-8921">
            <span class="alert-thumb road"><span class="material-symbols-outlined">edit_road</span></span>
            <span class="alert-copy"><small class="critical"><i></i> ALTA PRIORIDADE <time>Há 14 min</time></small><strong>Cratera em Faixa de Ônibus</strong><small>Av. Rebouças, próx. nº 2140</small><span class="alert-meta">Protocolo RPT-2026-4KQ7</span></span>
          </a>
          <a class="alert-item" routerLink="/ocorrencias/REC-2024-8914">
            <span class="alert-thumb tree"><span class="material-symbols-outlined">park</span></span>
            <span class="alert-copy"><small class="critical"><i></i> RISCO DE VIDA <time>Há 22 min</time></small><strong>Queda de Galho sobre via</strong><small>Rua Oscar Freire, alt. 980</small><span class="alert-meta">Protocolo RPT-2026-8921</span></span>
          </a>
          <a class="alert-item" routerLink="/ocorrencias/REC-2024-8908">
            <span class="alert-thumb drain"><span class="material-symbols-outlined">water</span></span>
            <span class="alert-copy"><small class="blue-text"><i></i> ALAGAMENTO <time>Há 35 min</time></small><strong>Bueiro Transbordando</strong><small>Rua Cardeal Arcoverde x Teodoro</small><span class="alert-meta">Protocolo RPT-2026-3M19</span></span>
          </a>
        </aside>

        <section class="detail-card neighborhood-card" id="mapa">
          <div class="card-heading"><div><h2>Densidade Territorial</h2><p>Bairros com maior número de chamados</p></div><span class="material-symbols-outlined muted-icon">location_on</span></div>
          <div class="map-preview"><span class="map-label">Radar Ativo: Zona Oeste / Centro</span><span><i></i> 3 focos de alta densidade</span></div>
          <ol class="district-list"><li><b>01</b><span>Pinheiros</span><strong>312</strong></li><li><b>02</b><span>Moema</span><strong>240</strong></li><li><b>03</b><span>Bela Vista</span><strong>192</strong></li><li><b>04</b><span>Sé (Centro Histórico)</span><strong>171</strong></li><li><b>05</b><span>Vila Madalena</span><strong>134</strong></li></ol>
        </section>

        <section class="detail-card service-card">
          <div class="card-heading"><div><h2>Tipologias de Serviços</h2><p>Proporção por categoria de intervenção</p></div><span class="material-symbols-outlined muted-icon">category</span></div>
          <div class="service-list">
            <div><span><i class="service-mark emerald"></i>Pavimentação e Tapa-Buracos</span><strong>42% (622)</strong><span class="progress"><i style="width: 42%"></i></span></div>
            <div><span><i class="service-mark yellow"></i>Iluminação Pública e Postes</span><strong>24% (356)</strong><span class="progress"><i style="width: 24%"></i></span></div>
            <div><span><i class="service-mark blue"></i>Poda e Manejo Arbóreo</span><strong>18% (267)</strong><span class="progress"><i style="width: 18%"></i></span></div>
            <div><span><i class="service-mark olive"></i>Bueiros, Bocas de Lobo &amp; Drenagem</span><strong>16% (237)</strong><span class="progress"><i style="width: 16%"></i></span></div>
          </div>
          <div class="contract-note"><span>Contratos Terceirizados Ativos</span><strong>6 Concessionárias</strong></div>
        </section>

        <section class="detail-card fleet-card" id="equipes">
          <div class="fleet-heading"><span class="material-symbols-outlined">local_shipping</span><div><h2>Gestão de Rotas &amp; Frotas</h2><p>Operações em Campo</p></div><span class="future-pill">Atualização<br />Futura (v2.0)</span></div>
          <p>Rastreamento em tempo real de equipes de rua, telemetria de veículos e roteirização inteligente estarão disponíveis na próxima atualização.</p>
          <div class="roadmap-note"><i></i> Em desenvolvimento • SMISU Roadmap</div>
        </section>
      </div>
      <p class="demo-caption">Dados ilustrativos para demonstração • Atualização de dados requer integração com a API de gestão municipal.</p>
    </div>
  `,
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent {
  exportNotice = false;
}
