import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { GradeResult } from '../../../core/models/grade-result.model';
import { GradingService } from '../../../core/services/grading.service';

@Component({
  selector: 'app-grade-report',
  imports: [RouterLink],
  templateUrl: './grade-report.html',
  styleUrl: './grade-report.css',
})
export class GradeReport {
  private readonly route = inject(ActivatedRoute);
  private readonly gradingService = inject(GradingService);

  protected readonly submissionId = this.route.snapshot.paramMap.get('submissionId')!;

  protected readonly result = signal<GradeResult | null>(null);
  protected readonly loading = signal(true);
  protected readonly notGraded = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly grading = signal(false);

  constructor() {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.notGraded.set(false);
    this.errorMessage.set(null);

    this.gradingService.getReport(this.submissionId).subscribe({
      next: (result) => {
        this.result.set(result);
        this.loading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        if (err.status === 404) {
          this.notGraded.set(true);
        } else {
          this.errorMessage.set('Failed to load the grade report.');
        }
      },
    });
  }

  protected gradeNow(): void {
    this.grading.set(true);
    this.errorMessage.set(null);

    this.gradingService.gradeSubmission(this.submissionId).subscribe({
      next: (result) => {
        this.result.set(result);
        this.notGraded.set(false);
        this.grading.set(false);
      },
      error: () => {
        this.grading.set(false);
        this.errorMessage.set(
          'Grading failed — the configured LLM providers may be rate-limited. Try again shortly.',
        );
      },
    });
  }

  protected percent(result: GradeResult): number {
    if (result.total_points_possible === 0) {
      return 0;
    }
    return Math.round((result.total_points_awarded / result.total_points_possible) * 100);
  }

  protected scoreBadgeClass(pct: number): string {
    if (pct >= 80) return 'badge-success';
    if (pct >= 50) return 'badge-warning';
    return 'badge-danger';
  }
}
