import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './services/auth.service';

function csrfToken(): string | null {
  const storedToken = sessionStorage.getItem('markup_csrf_token');
  if (storedToken) {
    return storedToken;
  }
  const cookie = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith('paper_checker_csrf='));
  return cookie ? decodeURIComponent(cookie.substring('paper_checker_csrf='.length)) : null;
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const credentialedRequest = request.clone({ withCredentials: true });
  const requestWithCsrf =
    csrfToken()
      ? credentialedRequest.clone({ setHeaders: { 'X-CSRF-Token': csrfToken()! } })
      : credentialedRequest;

  if (request.url.includes('/auth/')) {
    return next(requestWithCsrf);
  }

  return next(requestWithCsrf).pipe(
    catchError((error) => {
      if (error.status !== 401 || request.headers.has('X-Auth-Retry')) {
        return throwError(() => error);
      }
      return auth.refresh().pipe(
        switchMap(() => {
          const refreshedToken = csrfToken();
          const retryRequest = refreshedToken
            ? request.clone({
                withCredentials: true,
                setHeaders: { 'X-CSRF-Token': refreshedToken, 'X-Auth-Retry': '1' },
              })
            : request.clone({ withCredentials: true, setHeaders: { 'X-Auth-Retry': '1' } });
          return next(retryRequest);
        }),
        catchError((refreshError) => {
          auth.logout();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
