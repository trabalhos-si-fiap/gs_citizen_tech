import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';
import { signal } from '@angular/core';
import { authGuard, guestGuard } from './auth.guard';
import { AuthService } from './auth.service';

function setup(authenticated: boolean, profile: unknown, loadProfile = () => Promise.resolve({})) {
  const logout = vi.fn();
  TestBed.configureTestingModule({
    providers: [
      { provide: AuthService, useValue: { isAuthenticated: () => authenticated, profile: signal(profile), loadProfile, logout } },
      { provide: Router, useValue: { createUrlTree: (c: unknown[], e?: unknown) => ({ c, e }) as unknown as UrlTree } },
    ],
  });
  return { logout };
}

const run = (guard: typeof authGuard, url = '/ocorrencias') =>
  TestBed.runInInjectionContext(() => guard({} as never, { url } as never));

describe('guards', () => {
  it('authGuard sem sessão redireciona para /login com returnUrl', async () => {
    setup(false, null);
    expect(await run(authGuard)).toEqual({ c: ['/login'], e: { queryParams: { returnUrl: '/ocorrencias' } } });
  });

  it('authGuard com sessão e perfil libera', async () => {
    setup(true, { role: 'agency' });
    expect(await run(authGuard)).toBe(true);
  });

  it('authGuard com falha no perfil faz logout e redireciona', async () => {
    const { logout } = setup(true, null, () => Promise.reject(new Error('403')));
    expect(await run(authGuard, '/dashboard')).toEqual({ c: ['/login'], e: { queryParams: { returnUrl: '/dashboard' } } });
    expect(logout).toHaveBeenCalled();
  });

  it('guestGuard com sessão vai para /dashboard', () => {
    setup(true, null);
    expect(run(guestGuard)).toEqual({ c: ['/dashboard'], e: undefined });
  });

  it('guestGuard sem sessão libera /login', () => {
    setup(false, null);
    expect(run(guestGuard)).toBe(true);
  });
});
