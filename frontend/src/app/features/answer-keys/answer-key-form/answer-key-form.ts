import { Component, inject, signal } from '@angular/core';
import { FormArray, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AnswerKeyDraft } from '../../../core/models/answer-key.model';
import { AnswerKeyService } from '../../../core/services/answer-key.service';

@Component({
  selector: 'app-answer-key-form',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './answer-key-form.html',
  styleUrl: './answer-key-form.css',
})
export class AnswerKeyForm {
  private readonly fb: NonNullableFormBuilder = inject(NonNullableFormBuilder);
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  /** Present only on the /answer-keys/:id/edit route. */
  protected readonly answerKeyId = this.route.snapshot.paramMap.get('answerKeyId');
  protected readonly isEditMode = this.answerKeyId !== null;

  protected readonly submitting = signal(false);
  protected readonly loading = signal(this.isEditMode);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly bulkMcqCount = signal(5);
  protected readonly bulkMcqPoints = signal(1);

  protected readonly form = this.fb.group({
    title: this.fb.control('', Validators.required),
    mcq_answers: this.fb.array<FormGroup>([]),
    text_answers: this.fb.array<FormGroup>([]),
  });

  constructor() {
    if (this.answerKeyId) {
      this.answerKeyService.get(this.answerKeyId).subscribe({
        next: (key) => {
          this.form.controls.title.setValue(key.title);
          for (const mcq of key.mcq_answers) {
            this.mcqAnswers.push(
              this.fb.group({
                question_id: this.fb.control(mcq.question_id, Validators.required),
                correct_option: this.fb.control(mcq.correct_option, Validators.required),
                points: this.fb.control(mcq.points, [Validators.required, Validators.min(0)]),
              }),
            );
          }
          for (const text of key.text_answers) {
            const textGroup = this.fb.group({
              question_id: this.fb.control(text.question_id, Validators.required),
              reference_answer: this.fb.control(text.reference_answer, Validators.required),
              rubric: this.fb.array<FormGroup>([]),
            });
            for (const criterion of text.rubric) {
              this.rubricOf(textGroup).push(
                this.fb.group({
                  description: this.fb.control(criterion.description, Validators.required),
                  max_points: this.fb.control(criterion.max_points, [
                    Validators.required,
                    Validators.min(0),
                  ]),
                }),
              );
            }
            this.textAnswers.push(textGroup);
          }
          this.loading.set(false);
        },
        error: () => {
          this.loading.set(false);
          this.errorMessage.set('Could not load this answer key. It may have been deleted.');
        },
      });
    }
  }

  protected get mcqAnswers(): FormArray<FormGroup> {
    return this.form.controls.mcq_answers;
  }

  protected get textAnswers(): FormArray<FormGroup> {
    return this.form.controls.text_answers;
  }

  protected addMcqAnswer(): void {
    this.mcqAnswers.push(
      this.fb.group({
        question_id: this.fb.control('', Validators.required),
        correct_option: this.fb.control('', Validators.required),
        points: this.fb.control(1, [Validators.required, Validators.min(0)]),
      }),
    );
  }

  protected generateMcqAnswers(): void {
    const count = Math.floor(this.bulkMcqCount());
    if (count < 1) {
      return;
    }
    const startIndex = this.mcqAnswers.length;
    for (let i = 0; i < count; i++) {
      this.mcqAnswers.push(
        this.fb.group({
          question_id: this.fb.control(`q${startIndex + i + 1}`, Validators.required),
          correct_option: this.fb.control('', Validators.required),
          points: this.fb.control(this.bulkMcqPoints(), [Validators.required, Validators.min(0)]),
        }),
      );
    }
  }

  protected removeMcqAnswer(index: number): void {
    this.mcqAnswers.removeAt(index);
  }

  protected addTextAnswer(): void {
    this.textAnswers.push(
      this.fb.group({
        question_id: this.fb.control('', Validators.required),
        reference_answer: this.fb.control('', Validators.required),
        rubric: this.fb.array<FormGroup>([]),
      }),
    );
  }

  protected removeTextAnswer(index: number): void {
    this.textAnswers.removeAt(index);
  }

  protected rubricOf(textAnswer: FormGroup): FormArray<FormGroup> {
    return textAnswer.get('rubric') as FormArray<FormGroup>;
  }

  protected addRubricCriterion(textAnswer: FormGroup): void {
    this.rubricOf(textAnswer).push(
      this.fb.group({
        description: this.fb.control('', Validators.required),
        max_points: this.fb.control(1, [Validators.required, Validators.min(0)]),
      }),
    );
  }

  protected removeRubricCriterion(textAnswer: FormGroup, index: number): void {
    this.rubricOf(textAnswer).removeAt(index);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    const draft = this.form.getRawValue() as unknown as AnswerKeyDraft;

    if (this.answerKeyId) {
      this.answerKeyService.update(this.answerKeyId, draft).subscribe({
        next: () => this.router.navigate(['/answer-keys', this.answerKeyId, 'submissions']),
        error: () => {
          this.submitting.set(false);
          this.errorMessage.set(
            'Failed to save changes. Check that the backend is running and try again.',
          );
        },
      });
      return;
    }

    this.answerKeyService.create(draft).subscribe({
      next: (created) => this.router.navigate(['/answer-keys', created.id, 'submissions']),
      error: () => {
        this.submitting.set(false);
        this.errorMessage.set(
          'Failed to save the answer key. Check that the backend is running and try again.',
        );
      },
    });
  }
}
