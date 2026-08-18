import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { BatchDetail, BatchRow } from '../../../core/models/batch.model';
import { BatchService } from '../../../core/services/batch.service';

@Component({
  selector: 'app-batch-results',
  imports: [RouterLink],
  templateUrl: './batch-results.html',
  styleUrl: './batch-results.css',
})
export class BatchResults {
  private readonly route = inject(ActivatedRoute);
  private readonly batchService = inject(BatchService);

  protected readonly batchId = this.route.snapshot.paramMap.get('batchId')!;
  protected readonly csvUrl = this.batchService.csvDownloadUrl(this.batchId);

  protected readonly detail = signal<BatchDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly gradedCount = computed(
    () => this.detail()?.rows.filter((r) => r.result !== null).length ?? 0,
  );

  constructor() {
    this.batchService.get(this.batchId).subscribe({
      next: (detail) => {
        this.detail.set(detail);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('Could not load this batch.');
      },
    });
  }

  protected wrongAnswers(row: BatchRow): string {
    if (!row.result) return 'Not graded yet';
    const wrong = row.result.question_grades.filter((g) => g.points_awarded < g.points_possible);
    if (wrong.length === 0) return 'All correct';
    return wrong.map((g) => `${g.question_id}: ${g.feedback || 'incorrect'}`).join(' · ');
  }

  protected scoreLabel(row: BatchRow): string {
    if (!row.result) return '—';
    return `${row.result.total_points_awarded}/${row.result.total_points_possible}`;
  }
}
