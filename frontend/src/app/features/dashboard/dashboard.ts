import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { forkJoin, of, switchMap } from 'rxjs';
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

  /** Keys plus every submission filed against them — built only from existing endpoints. */
  private readonly data = toSignal(
    this.answerKeyService.list().pipe(
      switchMap((keys) =>
        keys.length === 0
          ? of({ keys, submissions: [] as Submission[][] })
          : forkJoin(
              keys.map((k) => this.submissionService.listForAnswerKey(k.id)),
            ).pipe(switchMap((submissions) => of({ keys, submissions }))),
      ),
    ),
    { initialValue: { keys: [] as AnswerKey[], submissions: [] as Submission[][] } },
  );

  protected readonly keys = computed(() => this.data().keys);

  protected readonly queue = computed<QueueRow[]>(() => {
    const { keys, submissions } = this.data();
    const rows: QueueRow[] = [];
    keys.forEach((key, i) => {
      (submissions[i] ?? []).forEach((submission) => {
        rows.push({
          submission,
          keyTitle: key.title,
          writtenCount: submission.text_responses.length,
        });
      });
    });
    return rows;
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
