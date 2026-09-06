import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';

interface AuthResponse {
  access_token: string;
  token_type: string;
  email: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly storageKey = 'markup_access_token';
  readonly email = signal<string | null>(sessionStorage.getItem('markup_email'));

  constructor() {
    // Remove tokens created by the previous persistent-storage implementation.
    localStorage.removeItem(this.storageKey);
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

  logout(): void {
    sessionStorage.removeItem(this.storageKey);
    sessionStorage.removeItem('markup_email');
    this.email.set(null);
  }

  isAuthenticated(): boolean {
    return Boolean(sessionStorage.getItem(this.storageKey));
  }

  token(): string | null {
    return sessionStorage.getItem(this.storageKey);
  }

  private store(response: AuthResponse): void {
    sessionStorage.setItem(this.storageKey, response.access_token);
    sessionStorage.setItem('markup_email', response.email);
    this.email.set(response.email);
  }
}
