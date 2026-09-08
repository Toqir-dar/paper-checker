import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';

interface AuthResponse {
  email: string;
  csrf_token: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly sessionKey = 'markup_authenticated';
  readonly email = signal<string | null>(sessionStorage.getItem('markup_email'));

  constructor() {
    // Remove tokens created by the previous persistent-storage implementation.
    localStorage.removeItem('markup_access_token');
    localStorage.removeItem('markup_email');
  }

  signup(email: string, password: string) {
    return this.http.post<AuthResponse>(`${environment.apiBaseUrl}/auth/signup`, { email, password }).pipe(
      tap((response) => this.store(response)),
    );
  }

  login(email: string, password: string) {
    return this.http.post<AuthResponse>(`${environment.apiBaseUrl}/auth/login`, { email, password }).pipe(
      tap((response) => this.store(response)),
    );
  }

  refresh() {
    return this.http.post<AuthResponse>(`${environment.apiBaseUrl}/auth/refresh`, {}).pipe(
      tap((response) => this.store(response)),
    );
  }

  logout(): void {
    this.http.post<void>(`${environment.apiBaseUrl}/auth/logout`, {}).subscribe();
    sessionStorage.removeItem(this.sessionKey);
    sessionStorage.removeItem('markup_email');
    sessionStorage.removeItem('markup_csrf_token');
    this.email.set(null);
  }

  isAuthenticated(): boolean {
    return sessionStorage.getItem(this.sessionKey) === 'true';
  }

  private store(response: AuthResponse): void {
    sessionStorage.setItem(this.sessionKey, 'true');
    sessionStorage.setItem('markup_email', response.email);
    sessionStorage.setItem('markup_csrf_token', response.csrf_token);
    this.email.set(response.email);
  }
}
