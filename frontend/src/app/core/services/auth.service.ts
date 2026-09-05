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
  readonly email = signal<string | null>(localStorage.getItem('markup_email'));

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
    localStorage.removeItem(this.storageKey);
    localStorage.removeItem('markup_email');
    this.email.set(null);
  }

  isAuthenticated(): boolean {
    return Boolean(localStorage.getItem(this.storageKey));
  }

  token(): string | null {
    return localStorage.getItem(this.storageKey);
  }

  private store(response: AuthResponse): void {
    localStorage.setItem(this.storageKey, response.access_token);
    localStorage.setItem('markup_email', response.email);
    this.email.set(response.email);
  }
}
