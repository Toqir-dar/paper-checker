import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Subject } from '../models/subject.model';

@Injectable({ providedIn: 'root' })
export class SubjectService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/subjects`;

  list(): Observable<Subject[]> {
    return this.http.get<Subject[]>(this.baseUrl);
  }

  create(name: string): Observable<Subject> {
    return this.http.post<Subject>(this.baseUrl, { name });
  }
}