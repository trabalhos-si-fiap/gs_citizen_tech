import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { API_BASE } from './api.config';
import { AuthService } from './auth.service';

const PUBLIC_PREFIXES = [`${API_BASE}/v1/auth/`, `${API_BASE}/v1/public/`];

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  if (PUBLIC_PREFIXES.some((prefix) => request.url.startsWith(prefix))) return next(request);

  const auth = inject(AuthService);
  const withToken = (req: HttpRequest<unknown>) => {
    const token = auth.accessToken;
    return token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
  };

  return next(withToken(request)).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) return throwError(() => error);
      return from(auth.refresh()).pipe(
        switchMap((refreshed) => {
          if (!refreshed) {
            auth.logout();
            return throwError(() => error);
          }
          return next(withToken(request));
        }),
      );
    }),
  );
};
