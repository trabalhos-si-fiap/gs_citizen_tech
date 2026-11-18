import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

type OccurrenceStatus = 'Aguardando Triagem' | 'Em Andamento' | 'Em Análise Técnica' | 'Resolvidos';

interface Occurrence {
  id: string;
  source: string;
  evidence: string;
  title: string;
  category: string;
  service: string;
  address: string;
  neighborhood: string;
  opened: string;
  sla: string;
  priority: 'Crítica' | 'Alta' | 'Média' | 'Baixa';
  status: OccurrenceStatus;
}

@Component({
  selector: 'app-occurrences',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="occurrences-page">
      <div class="occurrences-heading">
        <div>
          <div class="context-line"><span>MESA DE OPERAÇÕES &amp; ZELADORIA TÁTICA</span><i></i><span>PLUG-IN SMISU V4.2</span></div>
          <h1>Gestão de Ocorrências</h1>
        </div>
        <span class="registered-count">1.482 chamados registrados</span>
      </div>

      <section class="queue-stats" aria-label="Resumo das ocorrências">
        <article><span class="eyebrow">AGUARDANDO TRIAGEM</span><strong>43</strong><small class="critical-text">▲ 8 novos nos últimos 30min</small><span class="queue-icon yellow-icon"><span class="material-symbols-outlined">pending_actions</span></span></article>
        <article><span class="eyebrow">EM ATENDIMENTO DE RUA</span><strong class="blue-text">312</strong><span class="queue-icon blue-icon"><span class="material-symbols-outlined">engineering</span></span></article>
        <article><span class="eyebrow">SLA EM ALERTA CRÍTICO (&lt;12H)</span><strong class="critical-text">17</strong><small class="critical-text">Intervenção prioritária</small><span class="queue-icon red-icon"><span class="material-symbols-outlined">notification_important</span></span></article>
        <article><span class="eyebrow">RESOLVIDOS MÊS CORRENTE</span><strong class="green-text">1.038</strong><small class="green-text">94.2% dentro da meta pactuada</small><span class="queue-icon green-icon"><span class="material-symbols-outlined">task_alt</span></span></article>
      </section>

      <section class="filter-panel" aria-label="Filtros de ocorrências">
        <div class="filter-top">
          <label class="search-box"><span class="material-symbols-outlined">search</span><input type="search" [(ngModel)]="search" placeholder="Buscar protocolo, rua ou categoria..." aria-label="Buscar ocorrências" /></label>
          <div class="status-tabs" aria-label="Filtrar por status">
            <button type="button" [class.selected]="activeStatus === 'Todas'" (click)="activeStatus = 'Todas'">Todos <span>({{ rows.length }})</span></button>
            <button type="button" [class.selected]="activeStatus === 'Aguardando Triagem'" (click)="activeStatus = 'Aguardando Triagem'">Aguardando Triagem <span>43</span></button>
            <button type="button" [class.selected]="activeStatus === 'Em Andamento'" (click)="activeStatus = 'Em Andamento'">Em Andamento <span>312</span></button>
            <button type="button" [class.selected]="activeStatus === 'Em Análise Técnica'" (click)="activeStatus = 'Em Análise Técnica'">Em Análise Técnica <span>89</span></button>
            <button type="button" [class.selected]="activeStatus === 'Resolvidos'" (click)="activeStatus = 'Resolvidos'">Resolvidos <span>1.038</span></button>
          </div>
        </div>
        <div class="filter-bottom">
          <label><span class="eyebrow">PRIORIDADE</span><select [(ngModel)]="priorityFilter" aria-label="Filtrar por prioridade"><option value="">Todas as Prioridades</option><option>Crítica</option><option>Alta</option><option>Média</option><option>Baixa</option></select></label>
          <label><span class="eyebrow">CATEGORIA DE SERVIÇO</span><select [(ngModel)]="categoryFilter" aria-label="Filtrar por categoria"><option value="">Todas as Categorias</option><option>Pavimentação</option><option>Iluminação</option><option>Poda &amp; Manejo</option><option>Drenagem</option></select></label>
          <label><span class="eyebrow">SUBPREFEITURA / REGIÃO</span><select [(ngModel)]="neighborhoodFilter" aria-label="Filtrar por região"><option value="">Todas as Subprefeituras</option><option>Pinheiros</option><option>Sé</option><option>Mooca</option><option>Jardim América</option></select></label>
          <label><span class="eyebrow">JANELA SLA</span><select [(ngModel)]="slaFilter" aria-label="Filtrar por prazo de SLA"><option value="">Todos os Prazos</option><option value="critical">Em risco (&lt; 12h)</option><option value="normal">Dentro do prazo</option></select></label>
          <button class="clear-filters" type="button" (click)="clearFilters()"><span class="material-symbols-outlined">filter_alt_off</span> Limpar Filtros</button>
        </div>
      </section>

      <section class="occurrence-table-wrap">
        <table class="occurrence-table">
          <thead><tr><th><input type="checkbox" [checked]="allVisibleSelected" (change)="toggleAll($event)" aria-label="Selecionar todas as ocorrências visíveis" /></th><th>PROTOCOLO</th><th>EVIDÊNCIA</th><th>OCORRÊNCIA &amp; CATEGORIA</th><th>LOGRADOURO / BAIRRO</th><th>ABERTURA &amp; SLA</th><th>PRIORIDADE</th></tr></thead>
          <tbody>
            <tr *ngFor="let row of filteredRows">
              <td><input type="checkbox" [checked]="selectedIds.has(row.id)" (change)="toggleRow(row.id)" [attr.aria-label]="'Selecionar ocorrência ' + row.id" /></td>
              <td><a class="protocol-link" [routerLink]="['/ocorrencias', row.id]">{{ row.id }}</a><small>{{ row.source }}</small></td>
              <td><span class="table-evidence" [ngClass]="row.evidenceClass"><span class="material-symbols-outlined">{{ row.evidence }}</span><small>{{ row.photos }} fotos</small></span></td>
              <td><a class="occurrence-title" [routerLink]="['/ocorrencias', row.id]">{{ row.title }}</a><div class="category-label"><span>{{ row.category }}</span> • {{ row.service }}</div></td>
              <td><strong class="address">{{ row.address }}</strong><small>{{ row.neighborhood }} • Subpref. {{ row.neighborhood }}</small></td>
              <td><span class="opened-time">{{ row.opened }}</span><strong class="sla-time" [ngClass]="row.slaClass">{{ row.sla }}</strong><span class="sla-meter"><i [style.width]="row.slaWidth" [ngClass]="row.slaClass"></i></span></td>
              <td><span class="priority-pill" [ngClass]="row.priorityClass"><i></i>{{ row.priority }}</span></td>
            </tr>
            <tr *ngIf="filteredRows.length === 0"><td class="empty-state" colspan="7">Nenhuma ocorrência corresponde aos filtros selecionados.</td></tr>
          </tbody>
        </table>
        <footer class="table-footer">
          <span>Mostrando <strong>{{ filteredRows.length }}</strong> de <strong>1.482</strong> ocorrências<span *ngIf="selectedIds.size"> • {{ selectedIds.size }} selecionadas</span></span>
          <label>Itens por página: <select aria-label="Itens por página"><option>10</option><option>25</option><option>50</option></select></label>
          <nav aria-label="Paginação"><button type="button" aria-label="Página anterior" disabled>‹</button><button class="page-selected" type="button">1</button><button type="button">2</button><button type="button">3</button><span>…</span><button type="button">149</button><button type="button" aria-label="Próxima página">›</button></nav>
        </footer>
      </section>
      <p class="demo-caption">Dados ilustrativos para demonstração • Atualizações da fila requerem integração com o serviço de ocorrências.</p>
    </div>
  `,
  styleUrl: './occurrences.component.css',
})
export class OccurrencesComponent {
  readonly rows: (Occurrence & { evidenceClass: string; photos: number; slaClass: string; slaWidth: string; priorityClass: string })[] = [
    { id: 'REC-2024-8921', source: 'App Cidadão SP', evidence: 'edit_road', evidenceClass: 'road-evidence', photos: 3, title: 'Cratera profunda na pista central', category: 'Pavimentação', service: 'Tapa-Buraco Expresso', address: 'Av. Rebouças, 2130', neighborhood: 'Pinheiros', opened: 'Hoje, 07:15', sla: '2h restantes', priority: 'Crítica', status: 'Aguardando Triagem', slaClass: 'danger', slaWidth: '88%', priorityClass: 'priority-critical' },
    { id: 'REC-2024-8919', source: 'Central 156', evidence: 'traffic', evidenceClass: 'traffic-evidence', photos: 1, title: 'Poste sem luz em cruzamento movimentado', category: 'Iluminação', service: 'Braço de LED Queimado', address: 'Rua Augusta esq. c/ Peixoto Gomes', neighborhood: 'Sé', opened: 'Ontem, 21:40', sla: '14h restantes', priority: 'Alta', status: 'Em Andamento', slaClass: 'warning', slaWidth: '52%', priorityClass: 'priority-high' },
    { id: 'REC-2024-8914', source: 'Defesa Civil', evidence: 'park', evidenceClass: 'tree-evidence', photos: 4, title: 'Árvore de grande porte tombada na via', category: 'Poda & Manejo', service: 'Remoção Emergencial', address: 'Al. Gabriel Monteiro da Silva, 440', neighborhood: 'Jardim América', opened: 'Hoje, 05:30', sla: '1h restante', priority: 'Crítica', status: 'Em Análise Técnica', slaClass: 'danger', slaWidth: '93%', priorityClass: 'priority-critical' },
    { id: 'REC-2024-8908', source: 'App Cidadão SP', evidence: 'water', evidenceClass: 'drain-evidence', photos: 2, title: 'Bueiro entupido com risco iminente de alagamento', category: 'Drenagem', service: 'Desobstrução Boca de Lobo', address: 'Rua da Mooca, 1780', neighborhood: 'Mooca', opened: 'Ontem, 16:10', sla: '5h restantes', priority: 'Alta', status: 'Aguardando Triagem', slaClass: 'danger', slaWidth: '82%', priorityClass: 'priority-high' },
    { id: 'REC-2024-8899', source: 'Ofício Vereança 41', evidence: 'delete_sweep', evidenceClass: 'street-evidence', photos: 2, title: 'Descarte clandestino de entulho e resíduos', category: 'Limpeza Urbana', service: 'Ec ponto Volante', address: 'Av. Aricanduva, 5400', neighborhood: 'Aricanduva', opened: '24/10, 09:20', sla: '32h restantes', priority: 'Média', status: 'Em Andamento', slaClass: 'safe', slaWidth: '26%', priorityClass: 'priority-medium' },
    { id: 'REC-2024-8882', source: 'App Cidadão SP', evidence: 'signpost', evidenceClass: 'sign-evidence', photos: 1, title: 'Placa de trânsito tombada e vandalizada', category: 'Sinalização', service: 'Sinalização Vertical', address: 'R. Voluntários da Pátria, 1220', neighborhood: 'Santana', opened: '23/10, 14:00', sla: '48h restantes', priority: 'Baixa', status: 'Em Análise Técnica', slaClass: 'safe', slaWidth: '18%', priorityClass: 'priority-low' },
    { id: 'REC-2024-8840', source: 'App Cidadão SP', evidence: 'check_circle', evidenceClass: 'resolved-evidence', photos: 2, title: 'Buraco na faixa de ônibus', category: 'Pavimentação', service: 'Concluído com laudo fotográfico', address: 'Av. Brigadeiro Luís Antônio, 3400', neighborhood: 'Jardins', opened: 'Concluído, 24/10', sla: '100% SLA', priority: 'Alta', status: 'Resolvidos', slaClass: 'safe', slaWidth: '100%', priorityClass: 'priority-medium' },
  ];

  search = '';
  activeStatus = 'Todas';
  priorityFilter = '';
  categoryFilter = '';
  neighborhoodFilter = '';
  slaFilter = '';
  selectedIds = new Set<string>();

  get filteredRows() {
    const query = this.search.trim().toLocaleLowerCase('pt-BR');
    return this.rows.filter((row) =>
      (!query || `${row.id} ${row.title} ${row.address} ${row.neighborhood} ${row.category} ${row.service}`.toLocaleLowerCase('pt-BR').includes(query))
      && (this.activeStatus === 'Todas' || row.status === this.activeStatus)
      && (!this.priorityFilter || row.priority === this.priorityFilter)
      && (!this.categoryFilter || row.category === this.categoryFilter)
      && (!this.neighborhoodFilter || row.neighborhood === this.neighborhoodFilter)
      && (!this.slaFilter || (this.slaFilter === 'critical' ? row.slaClass === 'danger' : row.slaClass !== 'danger')),
    );
  }

  get allVisibleSelected(): boolean {
    return this.filteredRows.length > 0 && this.filteredRows.every((row) => this.selectedIds.has(row.id));
  }

  toggleRow(id: string): void {
    const next = new Set(this.selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.selectedIds = next;
  }

  toggleAll(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    const next = new Set(this.selectedIds);
    for (const row of this.filteredRows) {
      if (checked) next.add(row.id);
      else next.delete(row.id);
    }
    this.selectedIds = next;
  }

  clearFilters(): void {
    this.search = '';
    this.activeStatus = 'Todas';
    this.priorityFilter = '';
    this.categoryFilter = '';
    this.neighborhoodFilter = '';
    this.slaFilter = '';
  }
}
