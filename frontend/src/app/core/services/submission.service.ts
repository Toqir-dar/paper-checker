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

  /** Every submission across all answer keys, in one call. */
  list(): Observable<Submission[]> {
    return this.http.get<Submission[]>(this.baseUrl);
  }

  get(id: string): Observable<Submission> {
    return this.http.get<Submission>(`${this.baseUrl}/${id}`);
  }

  create(draft: SubmissionDraft): Observable<Submission> {
    return this.http.post<Submission>(this.baseUrl, draft);
  }

  /**
   * `studentName` is omitted by the batch-upload flow, which never asks for a
   * name per paper — the backend falls back to the roll number it detects.
   * `batchId` groups the created submission under a batch for the batch
   * results view/CSV.
   */
  uploadFile(
    answerKeyId: string,
    file: File,
    options?: { studentName?: string; batchId?: string },
  ): Observable<Submission> {
    const formData = new FormData();
    formData.append('answer_key_id', answerKeyId);
    if (options?.studentName) {
      formData.append('student_name', options.studentName);
    }
    if (options?.batchId) {
      formData.append('batch_id', options.batchId);
    }
    formData.append('file', file);
    return this.http.post<Submission>(`${this.baseUrl}/upload`, formData);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  /** GET endpoint, no API key required — usable directly as an <a href>, same
   * as BatchService.csvDownloadUrl. Covers every submission filed against this
   * answer key, not just ones grouped into a batch. */
  csvDownloadUrl(answerKeyId: string): string {
    const params = new HttpParams().set('answer_key_id', answerKeyId);
    return `${this.baseUrl}/csv?${params.toString()}`;
  }
}
