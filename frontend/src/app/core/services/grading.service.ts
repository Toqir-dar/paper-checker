import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { GradeResult } from '../models/grade-result.model';

@Injectable({ providedIn: 'root' })
export class GradingService {
  private readonly http = inject(HttpClient);

  gradeSubmission(submissionId: string): Observable<GradeResult> {
    return this.http.post<GradeResult>(`${environment.apiBaseUrl}/grading/${submissionId}`, {});
  }

  getReport(submissionId: string): Observable<GradeResult> {
    return this.http.get<GradeResult>(`${environment.apiBaseUrl}/reports/${submissionId}`);
  }

  /** Bakes in the teacher's point overrides (keyed by question_id) and marks
   * the report reviewed. Questions not present in `overrides` keep their
   * existing score. */
  confirmReport(submissionId: string, overrides: Record<string, number>): Observable<GradeResult> {
    return this.http.patch<GradeResult>(`${environment.apiBaseUrl}/reports/${submissionId}/confirm`, {
      overrides,
    });
  }
}
