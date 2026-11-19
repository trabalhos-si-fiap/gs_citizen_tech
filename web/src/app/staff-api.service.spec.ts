import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { API_BASE } from './api.config';
import { deadlineLabel } from './labels';
import { StaffApiError, StaffApiService } from './staff-api.service';

describe('StaffApiService', () => {
  let api: StaffApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(StaffApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('sends only the filters that are set when listing reports', async () => {
    const page = api.listReports({ status: 'em_andamento', category: '', overdue: true, q: '  buraco ', cursor: null, limit: 10 });

    const request = http.expectOne((req) => req.url === `${API_BASE}/v1/staff/reports`);
    expect(request.request.params.get('status')).toBe('em_andamento');
    expect(request.request.params.get('overdue')).toBe('true');
    expect(request.request.params.get('q')).toBe('buraco');
    expect(request.request.params.has('category')).toBe(false);
    expect(request.request.params.has('cursor')).toBe(false);
    request.flush({ items: [], next_cursor: null });
    await expect(page).resolves.toEqual({ items: [], next_cursor: null });
  });

  it('asks for every agency as redirect targets', async () => {
    const targets = api.redirectTargets();

    const request = http.expectOne((req) => req.url === `${API_BASE}/v1/staff/agencies`);
    expect(request.request.params.get('scope')).toBe('all');
    request.flush({ items: [{ id: 'a', name: 'A' }] });
    await expect(targets).resolves.toEqual([{ id: 'a', name: 'A' }]);
  });

  it('posts moderation decisions to the decision route', async () => {
    const result = api.moderate('r1', 'reject', { justification: 'ofensivo' });

    const request = http.expectOne(`${API_BASE}/v1/staff/moderation/r1/reject`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ justification: 'ofensivo' });
    request.flush({ id: 'r1' });
    await expect(result).resolves.toEqual({ id: 'r1' });
  });

  it('turns API errors into messages for the screen', async () => {
    const result = api.redirect('r1', { agency_id: 'x', justification: 'y' });

    http
      .expectOne(`${API_BASE}/v1/staff/reports/r1/redirect`)
      .flush({ error: { message: 'Não é possível redirecionar.' } }, { status: 409, statusText: 'Conflict' });
    await expect(result).rejects.toEqual(new StaffApiError(409, 'Não é possível redirecionar.'));
  });
});

describe('deadlineLabel', () => {
  const now = Date.parse('2026-11-18T12:00:00Z');

  it('reads backend deadlines without timezone as UTC', () => {
    expect(deadlineLabel('2026-11-18T17:00:00', now)).toBe('faltam 5h');
  });

  it('shows overdue deadlines', () => {
    expect(deadlineLabel('2026-11-18T10:00:00Z', now)).toBe('atrasado 2h');
    expect(deadlineLabel(null, now)).toBe('Sem prazo');
  });
});
