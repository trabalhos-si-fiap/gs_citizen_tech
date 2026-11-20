import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { OccurrencesComponent } from './occurrences.component';
import { StaffApiService } from './staff-api.service';
import { StaffReportItem } from './staff.models';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function item(overrides: Partial<StaffReportItem>): StaffReportItem {
  return {
    id: 'r1',
    protocol: 'RPT-2026-4KQ7TD',
    status: 'encaminhado',
    category: 'risco_urbano',
    urgency: 'alta',
    immediate_risk: false,
    description: 'Buraco na via',
    lat: -23.573806,
    lon: -46.623157,
    received_at: '2026-11-19T23:29:25.789511Z',
    deadline: null,
    overdue: false,
    agency: { id: 'zeladoria', name: 'Zeladoria' },
    confirmation_count: 0,
    address: null,
    ...overrides,
  };
}

async function render(items: StaffReportItem[]): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [OccurrencesComponent],
    providers: [
      provideRouter([]),
      {
        provide: StaffApiService,
        useValue: {
          listReports: () => Promise.resolve({ items, next_cursor: null }),
          summary: () => Promise.reject(new Error('sem resumo')),
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(OccurrencesComponent);
  fixture.detectChanges();
  await settle();
  fixture.detectChanges();
  return fixture.nativeElement;
}

async function renderLocationCells(items: StaffReportItem[]): Promise<HTMLElement[]> {
  return Array.from((await render(items)).querySelectorAll('strong.address'));
}

describe('OccurrencesComponent — coluna LOCAL / ÓRGÃO', () => {
  it('mostra o endereço e, sem ele, as coordenadas', async () => {
    const cells = await renderLocationCells([
      item({ id: 'r1', address: 'Rua Exemplo, 123 – Bairro, Cidade' }),
      item({ id: 'r2', address: null }),
    ]);

    expect(cells.map((cell) => cell.textContent?.trim())).toEqual([
      'Rua Exemplo, 123 – Bairro, Cidade',
      '-23.5738, -46.6232',
    ]);
  });

  it('exibe o endereço (texto vindo do aparelho) sem interpretar HTML', async () => {
    const [cell] = await renderLocationCells([item({ address: '<img src=x onerror="alert(1)">Rua X' })]);

    expect(cell.textContent?.trim()).toBe('<img src=x onerror="alert(1)">Rua X');
    expect(cell.querySelector('img')).toBeNull();
  });
});

describe('OccurrencesComponent — busca', () => {
  it('indica que a busca também procura no endereço', async () => {
    const page = await render([]);

    const input = page.querySelector('input[name="search"]') as HTMLInputElement;
    expect(input.placeholder).toBe('Buscar protocolo, descrição ou endereço e tecle Enter');
  });
});
