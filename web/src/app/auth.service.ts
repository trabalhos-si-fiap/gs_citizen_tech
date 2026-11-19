import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { API_BASE } from './api.config';
import { AuthError, AuthTokens, StaffProfile } from './auth.models';

const STORAGE_KEY = 'reclame_ja_tokens';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly tokens = signal<AuthTokens | null>(this.readStoredTokens());
  readonly profile = signal<StaffProfile | null>(null);
  readonly isAuthenticated = computed(() => this.tokens() !== null);

  private refreshInFlight: Promise<boolean> | null = null;

  get accessToken(): string | null {
    return this.tokens()?.access_token ?? null;
  }

  async requestCode(email: string): Promise<void> {
    try {
      await firstValueFrom(this.http.post(`${API_BASE}/v1/auth/login`, { email }));
    } catch (error) {
      throw this.toAuthError(error);
    }
  }

  async verifyCode(email: string, code: string, remember: boolean): Promise<void> {
    let tokens: AuthTokens;
    try {
      tokens = await firstValueFrom(this.http.post<AuthTokens>(`${API_BASE}/v1/auth/login`, { email, code }));
    } catch (error) {
      throw this.toAuthError(error);
    }
    this.saveTokens(tokens, remember);
    try {
      await this.loadProfile();
    } catch (error) {
      this.clearSession();
      throw error;
    }
  }

  async loadProfile(): Promise<StaffProfile> {
    try {
      const profile = await firstValueFrom(this.http.get<StaffProfile>(`${API_BASE}/v1/staff/me`));
      this.profile.set(profile);
      return profile;
    } catch (error) {
      throw this.toAuthError(error);
    }
  }

  /** Refresh token é de uso único: chamadas concorrentes compartilham a mesma promessa. */
  refresh(): Promise<boolean> {
    this.refreshInFlight ??= this.doRefresh().finally(() => (this.refreshInFlight = null));
    return this.refreshInFlight;
  }

  logout(): void {
    this.clearSession();
    void this.router.navigate(['/login']);
  }

  private async doRefresh(): Promise<boolean> {
    const current = this.tokens();
    if (!current) return false;
    try {
      const next = await firstValueFrom(
        this.http.post<AuthTokens>(`${API_BASE}/v1/auth/refresh`, { refresh_token: current.refresh_token }),
      );
      this.saveTokens(next, localStorage.getItem(STORAGE_KEY) !== null);
      return true;
    } catch {
      return false;
    }
  }

  private saveTokens(tokens: AuthTokens, remember: boolean): void {
    const { access_token, refresh_token, expires_in } = tokens;
    const stored: AuthTokens = { access_token, refresh_token, expires_in };
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    (remember ? localStorage : sessionStorage).setItem(STORAGE_KEY, JSON.stringify(stored));
    this.tokens.set(stored);
  }

  private clearSession(): void {
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    this.tokens.set(null);
    this.profile.set(null);
  }

  private readStoredTokens(): AuthTokens | null {
    const raw = localStorage.getItem(STORAGE_KEY) ?? sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as AuthTokens;
      return parsed.access_token && parsed.refresh_token ? parsed : null;
    } catch {
      return null;
    }
  }

  private toAuthError(error: unknown): AuthError {
    if (!(error instanceof HttpErrorResponse)) return new AuthError('unknown');
    switch (error.status) {
      case 0:
        return new AuthError('network');
      case 400:
        return new AuthError('consent');
      case 401:
        return new AuthError('invalid_code');
      case 403:
        return new AuthError('forbidden');
      case 503:
        return new AuthError('unavailable');
      default:
        return new AuthError('unknown');
    }
  }
}
