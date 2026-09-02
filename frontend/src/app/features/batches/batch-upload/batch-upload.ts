import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { BatchService } from '../../../core/services/batch.service';
import { GradingService } from '../../../core/services/grading.service';
import { SubmissionService } from '../../../core/services/submission.service';

type FileStatus = 'pending' | 'processing' | 'retrying' | 'done' | 'failed';

interface FileProgress {
  file: File;
  status: FileStatus;
  rollNumber?: string;
  score?: string;
  errorMessage?: string;
  progressDetail?: string;
}

/** Sequential concurrency of 1 prevents free-tier rate limit burst collisions. */
const CONCURRENCY = 1;
const MAX_ITEM_RETRIES = 2;
const RETRY_DELAY_MS = 3000;
const INTER_ITEM_DELAY_MS = 600;

@Component({
  selector: 'app-batch-upload',
  imports: [RouterLink],
  templateUrl: './batch-upload.html',
  styleUrl: './batch-upload.css',
})
export class BatchUpload {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly batchService = inject(BatchService);
  private readonly submissionService = inject(SubmissionService);
  private readonly gradingService = inject(GradingService);

  protected readonly answerKeyId = this.route.snapshot.paramMap.get('answerKeyId')!;

  protected readonly files = signal<FileProgress[]>([]);
  protected readonly running = signal(false);
  protected readonly batchId = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly doneCount = computed(() => this.files().filter((f) => f.status === 'done').length);
  protected readonly failedCount = computed(() => this.files().filter((f) => f.status === 'failed').length);
  protected readonly settledCount = computed(() => this.doneCount() + this.failedCount());

  protected onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const chosen = Array.from(input.files ?? []);
    this.files.set(chosen.map((file) => ({ file, status: 'pending' as const })));
    this.batchId.set(null);
    this.errorMessage.set(null);
  }

  protected start(): void {
    if (this.files().length === 0) {
      this.errorMessage.set('Select every scanned paper from the folder first.');
      return;
    }

    this.running.set(true);
    this.errorMessage.set(null);

    this.batchService.create(this.answerKeyId).subscribe({
      next: (batch) => {
        this.batchId.set(batch.id);
        const allIndices = Array.from({ length: this.files().length }, (_, i) => i);
        void this.runQueue(batch.id, allIndices);
      },
      error: () => {
        this.running.set(false);
        this.errorMessage.set('Could not start the batch. Check that the backend is running and try again.');
      },
    });
  }

  protected retryFailed(): void {
    const bId = this.batchId();
    if (!bId || this.running()) return;

    const failedIndices = this.files()
      .map((f, i) => (f.status === 'failed' ? i : -1))
      .filter((i) => i !== -1);

    if (failedIndices.length === 0) return;

    this.running.set(true);
    this.errorMessage.set(null);

    // Reset failed items to pending
    for (const idx of failedIndices) {
      this.setStatus(idx, { status: 'pending', errorMessage: undefined, progressDetail: undefined });
    }

    void this.runQueue(bId, failedIndices);
  }

  private async runQueue(batchId: string, indices: number[]): Promise<void> {
    const queue = [...indices];

    const worker = async (): Promise<void> => {
      let index: number | undefined;
      while ((index = queue.shift()) !== undefined) {
        await this.processOneWithRetries(batchId, index);
        // Small polite pause between papers to prevent rapid-fire burst rate limits
        if (queue.length > 0) {
          await new Promise((resolve) => setTimeout(resolve, INTER_ITEM_DELAY_MS));
        }
      }
    };

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    this.running.set(false);
  }

  private setStatus(index: number, patch: Partial<FileProgress>): void {
    this.files.update((list) => list.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  private async processOneWithRetries(batchId: string, index: number): Promise<void> {
    const file = this.files()[index].file;

    for (let attempt = 0; attempt <= MAX_ITEM_RETRIES; attempt++) {
      try {
        this.setStatus(index, {
          status: 'processing',
          progressDetail: 'Transcribing & matching answers…',
          errorMessage: undefined,
        });

        // 1. Upload & Vision extraction
        const submission = await firstValueFrom(
          this.submissionService.uploadFile(this.answerKeyId, file, { batchId })
        );

        this.setStatus(index, {
          status: 'processing',
          rollNumber: submission.roll_number || '(unreadable)',
          progressDetail: 'Grading answers…',
        });

        // 2. LLM / Similarity Grading
        const result = await firstValueFrom(this.gradingService.gradeSubmission(submission.id));

        this.setStatus(index, {
          status: 'done',
          rollNumber: submission.roll_number || '(unreadable)',
          score: `${result.total_points_awarded}/${result.total_points_possible}`,
          progressDetail: undefined,
          errorMessage: undefined,
        });
        return; // Success
      } catch (err: any) {
        const isRateLimit = err?.status === 503 || err?.status === 429;
        const isLastAttempt = attempt === MAX_ITEM_RETRIES;

        if (!isLastAttempt && isRateLimit) {
          this.setStatus(index, {
            status: 'retrying',
            errorMessage: `Rate limit hit — retrying in ${RETRY_DELAY_MS / 1000}s (attempt ${attempt + 1}/${MAX_ITEM_RETRIES})...`,
          });
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          continue;
        }

        const msg = isRateLimit
          ? 'Rate-limited across providers. Click "Retry failed" to retry.'
          : (err?.error?.detail || err?.message || 'Could not process this file');

        this.setStatus(index, {
          status: 'failed',
          errorMessage: msg,
          progressDetail: undefined,
        });
        return;
      }
    }
  }

  protected viewResults(): void {
    const id = this.batchId();
    if (id) {
      this.router.navigate(['/batches', id]);
    }
  }
}
