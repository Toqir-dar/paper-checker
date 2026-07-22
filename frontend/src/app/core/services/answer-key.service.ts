import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AnswerKey, AnswerKeyDraft } from '../models/answer-key.model';

@Injectable({ providedIn: 'root' })
export class AnswerKeyService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/answer-keys`;

  list(): Observable<AnswerKey[]> {
    return this.http.get<AnswerKey[]>(this.baseUrl);
  }

  get(id: string): Observable<AnswerKey> {
    return this.http.get<AnswerKey>(`${this.baseUrl}/${id}`);
  }

  create(draft: AnswerKeyDraft): Observable<AnswerKey> {
    return this.http.post<AnswerKey>(this.baseUrl, draft);
  }

  uploadFile(file: File): Observable<AnswerKey> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<AnswerKey>(`${this.baseUrl}/upload`, formData);
  }
}
