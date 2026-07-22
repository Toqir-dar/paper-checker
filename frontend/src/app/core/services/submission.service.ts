import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Submission, SubmissionDraft } from '../models/submission.model';

@Injectable({ providedIn: 'root' })
export class SubmissionService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/submissions`;

  listForAnswerKey(answerKeyId: string): Observable<Submission[]> {
    const params = new HttpParams().set('answer_key_id', answerKeyId);
    return this.http.get<Submission[]>(this.baseUrl, { params });
  }

  get(id: string): Observable<Submission> {
    return this.http.get<Submission>(`${this.baseUrl}/${id}`);
  }

  create(draft: SubmissionDraft): Observable<Submission> {
    return this.http.post<Submission>(this.baseUrl, draft);
  }

  uploadFile(answerKeyId: string, studentName: string, file: File): Observable<Submission> {
    const formData = new FormData();
    formData.append('answer_key_id', answerKeyId);
    formData.append('student_name', studentName);
    formData.append('file', file);
    return this.http.post<Submission>(`${this.baseUrl}/upload`, formData);
  }
}
