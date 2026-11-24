import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { BatchAnalytics } from '../models/batch-analytics.model';
import { Batch, BatchDetail } from '../models/batch.model';

@Injectable({ providedIn: 'root' })
export class BatchService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/batches`;

  create(answerKeyId: string): Observable<Batch> {
    return this.http.post<Batch>(this.baseUrl, { answer_key_id: answerKeyId });
  }

  listForAnswerKey(answerKeyId: string): Observable<Batch[]> {
    const params = new HttpParams().set('answer_key_id', answerKeyId);
    return this.http.get<Batch[]>(this.baseUrl, { params });
  }

  get(id: string): Observable<BatchDetail> {
    return this.http.get<BatchDetail>(`${this.baseUrl}/${id}`);
  }

  runAnalytics(id: string, itemsetMethod: 'apriori' | 'pcy' = 'apriori'): Observable<BatchAnalytics> {
    const params = new HttpParams().set('itemset_method', itemsetMethod);
    return this.http.post<BatchAnalytics>(`${this.baseUrl}/${id}/analytics`, null, { params });
  }

  getAnalytics(id: string): Observable<BatchAnalytics> {
    return this.http.get<BatchAnalytics>(`${this.baseUrl}/${id}/analytics`);
  }

  /** GET endpoints carry no API key requirement, so this can be used directly
   * as an <a href> — no need to fetch + blob it through HttpClient. */
  csvDownloadUrl(id: string): string {
    return `${this.baseUrl}/${id}/csv`;
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
