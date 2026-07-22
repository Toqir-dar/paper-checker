import { Component, inject, signal } from '@angular/core';
import { FormArray, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AnswerKey } from '../../../core/models/answer-key.model';
import { AnswerKeyService } from '../../../core/services/answer-key.service';
import { SubmissionDraft } from '../../../core/models/submission.model';
import { SubmissionService } from '../../../core/services/submission.service';

@Component({
  selector: 'app-submission-form',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './submission-form.html',
  styleUrl: './submission-form.css',
})
export class SubmissionForm {
  private readonly fb: NonNullableFormBuilder = inject(NonNullableFormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly submissionService = inject(SubmissionService);
  private readonly router = inject(Router);

  protected readonly answerKeyId = this.route.snapshot.paramMap.get('answerKeyId')!;
  protected readonly answerKey = signal<AnswerKey | null>(null);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly submitting = signal(false);
  protected readonly submitError = signal<string | null>(null);

  protected readonly form = this.fb.group({
    student_name: this.fb.control('', Validators.required),
    mcq_responses: this.fb.array<FormGroup>([]),
    text_responses: this.fb.array<FormGroup>([]),
  });

  constructor() {
    this.answerKeyService.get(this.answerKeyId).subscribe({
      next: (key) => {
        this.answerKey.set(key);
        this.buildResponseControls(key);
        this.loading.set(false);
      },
      error: () => {
        this.loadError.set('Could not load the answer key this submission belongs to.');
        this.loading.set(false);
      },
    });
  }

  protected get mcqResponses(): FormArray<FormGroup> {
    return this.form.controls.mcq_responses;
  }

  protected get textResponses(): FormArray<FormGroup> {
    return this.form.controls.text_responses;
  }

  protected mcqQuestionId(index: number): string {
    return this.answerKey()?.mcq_answers[index]?.question_id ?? '';
  }

  protected textQuestionId(index: number): string {
    return this.answerKey()?.text_answers[index]?.question_id ?? '';
  }

  private buildResponseControls(key: AnswerKey): void {
    for (const mcq of key.mcq_answers) {
      this.mcqResponses.push(
        this.fb.group({
          question_id: this.fb.control(mcq.question_id),
          selected_option: this.fb.control('', Validators.required),
        }),
      );
    }
    for (const textAnswer of key.text_answers) {
      this.textResponses.push(
        this.fb.group({
          question_id: this.fb.control(textAnswer.question_id),
          answer_text: this.fb.control('', Validators.required),
        }),
      );
    }
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.submitError.set(null);

    const draft = {
      ...this.form.getRawValue(),
      answer_key_id: this.answerKeyId,
    } as unknown as SubmissionDraft;

    this.submissionService.create(draft).subscribe({
        next: () => this.router.navigate(['/answer-keys', this.answerKeyId, 'submissions']),
        error: () => {
          this.submitting.set(false);
          this.submitError.set(
            'Failed to save the submission. Check that the backend is running and try again.',
          );
        },
      });
  }
}
