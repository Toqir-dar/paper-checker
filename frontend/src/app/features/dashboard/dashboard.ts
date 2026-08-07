import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { AnswerKey } from '../../core/models/answer-key.model';
import { Submission } from '../../core/models/submission.model';
import { AnswerKeyService } from '../../core/services/answer-key.service';
import { SubmissionService } from '../../core/services/submission.service';

/** One paper waiting for a human read, joined to the key it was graded against. */
export interface QueueRow {
  submission: Submission;
  keyTitle: string;
  /** Written answers carry judgement; MCQs don't. This is what's worth your time. */
  writtenCount: number;
}

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard {
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly submissionService = inject(SubmissionService);

  /** Keys plus every submission filed against them — two calls total, not one per key. */
  private readonly data = toSignal(
    forkJoin({
      keys: this.answerKeyService.list(),
      submissions: this.submissionService.list(),
    }),
    { initialValue: { keys: [] as AnswerKey[], submissions: [] as Submission[] } },
  );

  protected readonly keys = computed(() => this.data().keys);

  protected readonly queue = computed<QueueRow[]>(() => {
    const { keys, submissions } = this.data();
    const titleByKeyId = new Map(keys.map((k) => [k.id, k.title]));
    return submissions
      .filter((submission) => titleByKeyId.has(submission.answer_key_id))
      .map((submission) => ({
        submission,
        keyTitle: titleByKeyId.get(submission.answer_key_id)!,
        writtenCount: submission.text_responses.length,
      }));
  });

  protected readonly paperCount = computed(() => this.queue().length);

  protected readonly judgementCount = computed(() =>
    this.queue().reduce((n, r) => n + r.writtenCount, 0),
  );

  protected readonly today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });

  protected index(i: number): string {
    return String(i + 1).padStart(2, '0');
  }
}
