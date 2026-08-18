import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Batch } from '../../../core/models/batch.model';
import { Submission } from '../../../core/models/submission.model';
import { AnswerKeyService } from '../../../core/services/answer-key.service';
import { BatchService } from '../../../core/services/batch.service';
import { GradingService } from '../../../core/services/grading.service';
import { SubmissionService } from '../../../core/services/submission.service';

@Component({
  selector: 'app-submission-list',
  imports: [RouterLink, DatePipe],
  templateUrl: './submission-list.html',
  styleUrl: './submission-list.css',
})
export class SubmissionList {
  private readonly route = inject(ActivatedRoute);
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly submissionService = inject(SubmissionService);
  private readonly gradingService = inject(GradingService);
  private readonly batchService = inject(BatchService);
  private readonly router = inject(Router);

  protected readonly answerKeyId = this.route.snapshot.paramMap.get('answerKeyId')!;

  protected readonly answerKey = toSignal(this.answerKeyService.get(this.answerKeyId));
  protected readonly csvUrl = this.submissionService.csvDownloadUrl(this.answerKeyId);
  protected readonly submissions = signal<Submission[]>([]);
  protected readonly batches = signal<Batch[]>([]);

  protected readonly gradingId = signal<string | null>(null);
  protected readonly deletingId = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  constructor() {
    this.submissionService
      .listForAnswerKey(this.answerKeyId)
      .subscribe((submissions) => this.submissions.set(submissions));
    this.batchService.listForAnswerKey(this.answerKeyId).subscribe((batches) => this.batches.set(batches));
  }

  protected grade(submissionId: string): void {
    this.gradingId.set(submissionId);
    this.errorMessage.set(null);

    this.gradingService.gradeSubmission(submissionId).subscribe({
      next: () => {
        this.gradingId.set(null);
        this.router.navigate(['/submissions', submissionId, 'report']);
      },
      error: () => {
        this.gradingId.set(null);
        this.errorMessage.set(
          'Grading failed — the configured LLM providers may be rate-limited. Try again shortly.',
        );
      },
    });
  }

  protected delete(submission: Submission): void {
    const confirmed = confirm(`Delete ${submission.student_name}'s submission and its grade?`);
    if (!confirmed) {
      return;
    }

    this.deletingId.set(submission.id);
    this.errorMessage.set(null);
    this.submissionService.delete(submission.id).subscribe({
      next: () => {
        this.submissions.update((subs) => subs.filter((s) => s.id !== submission.id));
        this.deletingId.set(null);
      },
      error: () => {
        this.deletingId.set(null);
        this.errorMessage.set('Could not delete this submission. Try again.');
      },
    });
  }
}
