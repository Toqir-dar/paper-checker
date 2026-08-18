import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { BatchService } from '../../../core/services/batch.service';
import { GradingService } from '../../../core/services/grading.service';
import { SubmissionService } from '../../../core/services/submission.service';

type FileStatus = 'pending' | 'processing' | 'done' | 'failed';

interface FileProgress {
  file: File;
  status: FileStatus;
  rollNumber?: string;
  score?: string;
  errorMessage?: string;
}

/** How many papers to upload+grade at once. Free-tier vision/LLM providers
 * rate-limit per key — firing every file at once just exhausts the fallback
 * chain faster, it doesn't finish the batch any sooner. */
const CONCURRENCY = 3;

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
        void this.runQueue(batch.id);
      },
      error: () => {
        this.running.set(false);
        this.errorMessage.set('Could not start the batch. Check that the backend is running and try again.');
      },
    });
  }

  /** A fixed-size pool of workers pulling from a shared index queue — the
   * simplest way to cap concurrency without a library. */
  private async runQueue(batchId: string): Promise<void> {
    const queue = Array.from({ length: this.files().length }, (_, i) => i);

    const worker = async (): Promise<void> => {
      let index: number | undefined;
      while ((index = queue.shift()) !== undefined) {
        await this.processOne(batchId, index);
      }
    };

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    this.running.set(false);
  }

  private setStatus(index: number, patch: Partial<FileProgress>): void {
    this.files.update((list) => list.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  /** Upload + grade one paper. Never rejects — a failure is recorded on the
   * row so one bad scan doesn't abort the rest of the batch. */
  private processOne(batchId: string, index: number): Promise<void> {
    this.setStatus(index, { status: 'processing' });
    const file = this.files()[index].file;

    return new Promise((resolve) => {
      this.submissionService.uploadFile(this.answerKeyId, file, { batchId }).subscribe({
        next: (submission) => {
          this.gradingService.gradeSubmission(submission.id).subscribe({
            next: (result) => {
              this.setStatus(index, {
                status: 'done',
                rollNumber: submission.roll_number || '(unreadable)',
                score: `${result.total_points_awarded}/${result.total_points_possible}`,
              });
              resolve();
            },
            error: () => {
              this.setStatus(index, {
                status: 'failed',
                rollNumber: submission.roll_number || '(unreadable)',
                errorMessage: 'Read OK, but grading failed — rate-limited?',
              });
              resolve();
            },
          });
        },
        error: (err) => {
          this.setStatus(index, {
            status: 'failed',
            errorMessage:
              err.status === 503 ? 'Vision model rate-limited' : 'Could not read this file',
          });
          resolve();
        },
      });
    });
  }

  protected viewResults(): void {
    const id = this.batchId();
    if (id) {
      this.router.navigate(['/batches', id]);
    }
  }
}
