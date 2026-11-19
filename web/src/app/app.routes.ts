import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './auth.guard';
import { DashboardComponent } from './dashboard.component';
import { LoginComponent } from './login.component';
import { ModerationComponent } from './moderation.component';
import { OccurrenceDetailComponent } from './occurrence-detail.component';
import { OccurrencesComponent } from './occurrences.component';
import { PublicMetricsComponent } from './public-metrics.component';
import { ShellComponent } from './shell.component';

export const appRoutes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: 'login', component: LoginComponent, canActivate: [guestGuard], title: 'Acesso institucional | Reclame Já' },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: 'dashboard', component: DashboardComponent, title: 'Painel de controle | Reclame Já' },
      { path: 'ocorrencias', component: OccurrencesComponent, title: 'Gestão de ocorrências | Reclame Já' },
      { path: 'ocorrencias/:id', component: OccurrenceDetailComponent, title: 'Detalhe da ocorrência | Reclame Já' },
      { path: 'moderacao', component: ModerationComponent, title: 'Moderação | Reclame Já' },
      { path: 'indicadores', component: PublicMetricsComponent, title: 'Indicadores públicos | Reclame Já' },
    ],
  },
  { path: '**', redirectTo: 'login' },
];
