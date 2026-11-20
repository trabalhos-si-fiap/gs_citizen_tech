import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PublicMetricsComponent } from './public-metrics.component';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

const metrics = {
  totals: { reports: 109, avg_response_hours: 0.87, resolution_rate: 0.193, recurrence: 2 },
  by_agency: [
    { agency: { id: 'a1', name: 'Prefeitura Demo – Zeladoria' }, reports: 71, avg_response_hours: 0.5, resolution_rate: 0.25 },
  ],
};

describe('PublicMetricsComponent', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows the indicators as soon as the API answers, without any click', async () => {
    // Como na rede de verdade, a resposta chega depois do primeiro ciclo de renderização.
    vi.stubGlobal('fetch', vi.fn(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30));
      return new Response(JSON.stringify(metrics), { status: 200 });
    }));
    const fixture = TestBed.createComponent(PublicMetricsComponent);
    fixture.autoDetectChanges();

    // Sem clique nem detectChanges manual: só o tempo passando, como no navegador.
    await new Promise((resolve) => setTimeout(resolve, 120));
    await settle();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('109');
    expect(text).toContain('19.3%');
    expect(text).toContain('Prefeitura Demo – Zeladoria');
  });
});
