export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface StaffProfile {
  id: string;
  email: string | null;
  role: string;
  scope: 'agency' | 'all';
  agency: { id: string; name: string } | null;
}

export type AuthErrorKind = 'consent' | 'invalid_code' | 'forbidden' | 'unavailable' | 'network' | 'unknown';

export class AuthError extends Error {
  constructor(readonly kind: AuthErrorKind) {
    super(kind);
  }
}

export const ROLE_LABELS: Record<string, string> = {
  agency: 'Operador do órgão',
  manager: 'Gestor',
  moderator: 'Moderador',
  admin: 'Administrador',
};
