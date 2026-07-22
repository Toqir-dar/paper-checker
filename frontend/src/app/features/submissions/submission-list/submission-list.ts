import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AnswerKeyService } from '../../../core/services/answer-key.service';
import { GradingService } from '../../../core/services/grading.service';
import { SubmissionService } from '../../../core/services/submission.service';

@Component({
  selector: 'app-submission-list',
  imports: [RouterLink],
  templateUrl: './submission-list.html',
  styleUrl: './submission-list.css',
})
export class SubmissionList {
  private readonly route = inject(ActivatedRoute);
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly submissionService = inject(SubmissionService);
  private readonly gradingService = inject(GradingService);
  private readonly router = inject(Router);

  protected readonly answerKeyId = this.route.snapshot.paramMap.get('answerKeyId')!;

  protected readonly answerKey = toSignal(this.answerKeyService.get(this.answerKeyId));
  protected readonly submissions = toSignal(
    this.submissionService.listForAnswerKey(this.answerKeyId),
    { initialValue: [] },
  );

  protected readonly gradingId = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

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
}
