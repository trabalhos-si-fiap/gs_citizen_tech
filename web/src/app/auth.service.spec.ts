import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { API_BASE } from './api.config';
import { AuthError } from './auth.models';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

const TOKENS = { access_token: 'a1', refresh_token: 'r1', expires_in: 900, user: {} };
const PROFILE = { id: '1', email: 's@x.br', role: 'agency', scope: 'agency', agency: { id: 'ag', name: 'Órgão' } };

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() { return data.size; },
    clear: () => data.clear(),
    getItem: (k: string) => data.get(k) ?? null,
    key: (i: number) => [...data.keys()][i] ?? null,
    removeItem: (k: string) => void data.delete(k),
    setItem: (k: string, v: string) => void data.set(k, String(v)),
  };
}

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage());
    vi.stubGlobal('sessionStorage', memoryStorage());
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.unstubAllGlobals();
  });

  async function login(remember = true): Promise<void> {
    const done = auth.verifyCode('s@x.br', '123456', remember);
    http.expectOne(`${API_BASE}/v1/auth/login`).flush(TOKENS);
    await Promise.resolve();
    http.expectOne(`${API_BASE}/v1/staff/me`).flush(PROFILE);
    await done;
  }

  it('fluxo feliz: salva tokens e carrega perfil', async () => {
    await login(true);
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.profile()?.agency?.name).toBe('Órgão');
    expect(localStorage.getItem('reclame_ja_tokens')).toContain('a1');
  });

  it('sem "manter conectado" usa sessionStorage', async () => {
    await login(false);
    expect(localStorage.getItem('reclame_ja_tokens')).toBeNull();
    expect(sessionStorage.getItem('reclame_ja_tokens')).toContain('a1');
  });

  it('401 no código vira invalid_code', async () => {
    const done = auth.verifyCode('s@x.br', '000000', true);
    http.expectOne(`${API_BASE}/v1/auth/login`).flush({}, { status: 401, statusText: 'Unauthorized' });
    await expect(done).rejects.toMatchObject({ kind: 'invalid_code' });
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('403 em /staff/me descarta tokens', async () => {
    const done = auth.verifyCode('c@x.br', '123456', true);
    http.expectOne(`${API_BASE}/v1/auth/login`).flush(TOKENS);
    await Promise.resolve();
    http.expectOne(`${API_BASE}/v1/staff/me`).flush({}, { status: 403, statusText: 'Forbidden' });
    await expect(done).rejects.toBeInstanceOf(AuthError);
    expect(auth.isAuthenticated()).toBe(false);
    expect(localStorage.getItem('reclame_ja_tokens')).toBeNull();
  });

  it('refresh concorrente usa uma única chamada', async () => {
    await login(true);
    const first = auth.refresh();
    const second = auth.refresh();
    http.expectOne(`${API_BASE}/v1/auth/refresh`).flush({ ...TOKENS, access_token: 'a2', refresh_token: 'r2' });
    expect(await first).toBe(true);
    expect(await second).toBe(true);
    expect(auth.accessToken).toBe('a2');
  });

  it('401 em rota protegida faz refresh e repete a requisição', async () => {
    await login(true);
    const result = new Promise((resolve) => TestBed.inject(AuthService)['http'].get(`${API_BASE}/v1/staff/summary`).subscribe(resolve));
    const first = http.expectOne(`${API_BASE}/v1/staff/summary`);
    expect(first.request.headers.get('Authorization')).toBe('Bearer a1');
    first.flush({}, { status: 401, statusText: 'Unauthorized' });
    await Promise.resolve();
    http.expectOne(`${API_BASE}/v1/auth/refresh`).flush({ ...TOKENS, access_token: 'a2', refresh_token: 'r2' });
    await new Promise((r) => setTimeout(r));
    const retry = http.expectOne(`${API_BASE}/v1/staff/summary`);
    expect(retry.request.headers.get('Authorization')).toBe('Bearer a2');
    retry.flush({ total: 1 });
    await result;
  });

  it('refresh inválido faz logout', async () => {
    await login(true);
    const done = auth.refresh();
    http.expectOne(`${API_BASE}/v1/auth/refresh`).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(await done).toBe(false);
  });
});
