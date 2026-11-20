import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { AuthService } from './auth.service';
import { OccurrenceDetailComponent } from './occurrence-detail.component';
import { StaffApiService } from './staff-api.service';
import { ReportDetail } from './staff.models';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function report(overrides: Partial<ReportDetail>): ReportDetail {
  return {
    id: 'r1',
    protocol: 'RPT-2026-4KQ7TD',
    status: 'encaminhado',
    category: 'risco_urbano',
    lat: -23.573806,
    lon: -46.623157,
    received_at: '2026-11-19T23:29:25.789511Z',
    group_id: 'r1',
    confirmation_count: 0,
    description: 'Buraco na via',
    address: null,
    photo_url: null,
    anonymous: false,
    has_photo: false,
    triage_state: 'confirmed',
    classification: null,
    agency: null,
    deadline: null,
    timeline: [],
    ...overrides,
  };
}

async function renderMapCard(detail: ReportDetail): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path: 'ocorrencias/:id', component: OccurrenceDetailComponent }]),
      { provide: StaffApiService, useValue: { detail: () => Promise.resolve(detail), redirectTargets: () => Promise.resolve([]) } },
      { provide: AuthService, useValue: { profile: signal({ role: 'manager', agency: null }) } },
    ],
  });
  const harness = await RouterTestingHarness.create();
  await harness.navigateByUrl('/ocorrencias/r1', OccurrenceDetailComponent);
  await settle();
  harness.detectChanges();
  return harness.routeNativeElement!.querySelector('section.map-card') as HTMLElement;
}

describe('OccurrenceDetailComponent — card Localização', () => {
  it('mostra o endereço como linha principal e as coordenadas como linha secundária', async () => {
    const card = await renderMapCard(report({ address: 'Rua Exemplo, 123 – Bairro, Cidade' }));

    expect(card.querySelector('.location-address')?.textContent?.trim()).toBe('Rua Exemplo, 123 – Bairro, Cidade');
    expect(card.querySelector('.location-coordinates')?.textContent?.trim()).toBe('-23.57381, -46.62316');
    expect(card.querySelector('a')?.textContent).toContain('Abrir no mapa');
    expect(card.querySelector('iframe.report-map')).not.toBeNull();
  });

  it('sem endereço (reporte antigo) mostra só as coordenadas', async () => {
    const card = await renderMapCard(report({ address: null }));

    expect(card.querySelector('.location-address')?.textContent?.trim()).toBe('-23.57381, -46.62316');
    expect(card.querySelector('.location-coordinates')).toBeNull();
  });
});
