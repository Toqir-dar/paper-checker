import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { BatchAnalytics } from '../../../core/models/batch-analytics.model';
import { BatchDetail, BatchRow } from '../../../core/models/batch.model';
import { BatchService } from '../../../core/services/batch.service';

type AnalyticsTab = 'overview' | 'duplicates' | 'clusters' | 'patterns' | 'samples';

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
  protected readonly analytics = signal<BatchAnalytics | null>(null);
  protected readonly loading = signal(true);
  protected readonly analyticsLoading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly analyticsError = signal<string | null>(null);
  protected readonly activeTab = signal<AnalyticsTab>('overview');

  protected readonly gradedCount = computed(
    () => this.detail()?.rows.filter((r) => r.result !== null).length ?? 0,
  );

  protected readonly clusterBySubmission = computed(() => {
    const map = new Map<string, number>();
    for (const c of this.analytics()?.clusters ?? []) {
      map.set(c.submission_id, c.cluster_id);
    }
    return map;
  });

  constructor() {
    this.batchService.get(this.batchId).subscribe({
      next: (detail) => {
        this.detail.set(detail);
        this.loading.set(false);
        this.batchService.getAnalytics(this.batchId).subscribe({
          next: (a) => this.analytics.set(a),
          error: () => {
            /* none yet — teacher can run analytics */
          },
        });
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('Could not load this batch.');
      },
    });
  }

  protected setTab(tab: AnalyticsTab): void {
    this.activeTab.set(tab);
  }

  protected runAnalytics(): void {
    this.analyticsLoading.set(true);
    this.analyticsError.set(null);
    this.batchService.runAnalytics(this.batchId).subscribe({
      next: (a) => {
        this.analytics.set(a);
        this.analyticsLoading.set(false);
        this.activeTab.set('duplicates');
      },
      error: () => {
        this.analyticsLoading.set(false);
        this.analyticsError.set('Analytics job failed. Grade papers first, then retry.');
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

  protected clusterLabel(row: BatchRow): string {
    const id = row.submission.id ? this.clusterBySubmission().get(row.submission.id) : undefined;
    return id === undefined ? '' : `C${id}`;
  }
}
