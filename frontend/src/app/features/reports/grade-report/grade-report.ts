import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AnswerKey } from '../../../core/models/answer-key.model';
import { CriterionGrade, GradeResult, QuestionGrade } from '../../../core/models/grade-result.model';
import { Submission } from '../../../core/models/submission.model';
import { AnswerKeyService } from '../../../core/services/answer-key.service';
import { GradingService } from '../../../core/services/grading.service';
import { SubmissionService } from '../../../core/services/submission.service';

/** Why a question is worth a second look. Derived — nothing extra is asked of the API. */
export type Flag = 'numbering' | 'partial' | null;

@Component({
  selector: 'app-grade-report',
  imports: [RouterLink],
  templateUrl: './grade-report.html',
  styleUrl: './grade-report.css',
})
export class GradeReport {
  private readonly route = inject(ActivatedRoute);
  private readonly gradingService = inject(GradingService);
  private readonly submissionService = inject(SubmissionService);
  private readonly answerKeyService = inject(AnswerKeyService);

  protected readonly submissionId = this.route.snapshot.paramMap.get('submissionId')!;

  protected readonly result = signal<GradeResult | null>(null);
  protected readonly submission = signal<Submission | null>(null);
  protected readonly answerKey = signal<AnswerKey | null>(null);
  protected readonly loading = signal(true);
  protected readonly notGraded = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly grading = signal(false);
  protected readonly flaggedOnly = signal(false);
  protected readonly confirming = signal(false);
  // Kept separate from `errorMessage`, which swaps out the whole review view
  // on failure — a confirm failure should leave the report visible with an
  // inline note, not blank the page the teacher is looking at.
  protected readonly confirmError = signal<string | null>(null);

  /** Teacher overrides, keyed by question id. Cleared whenever the paper is re-graded. */
  private readonly overrides = signal<Record<string, number>>({});

  constructor() {
    this.load();
  }

  // ---------------------------------------------------------------- loading

  private load(): void {
    this.loading.set(true);
    this.notGraded.set(false);
    this.errorMessage.set(null);

    this.gradingService.getReport(this.submissionId).subscribe({
      next: (result) => this.onReport(result),
      error: (err: HttpErrorResponse) => {
        this.loading.set(false);
        if (err.status === 404) {
          this.notGraded.set(true);
        } else {
          this.errorMessage.set('Failed to load the grade report.');
        }
      },
    });
  }

  private onReport(result: GradeResult): void {
    this.result.set(result);
    this.overrides.set({});
    this.confirmError.set(null);
    this.loading.set(false);

    // What the student actually wrote, and what the key expects — both are needed
    // to review a judgement rather than just trust it.
    this.submissionService.get(result.submission_id).subscribe({
      next: (s) => this.submission.set(s),
      error: () => this.submission.set(null),
    });
    this.answerKeyService.get(result.answer_key_id).subscribe({
      next: (k) => this.answerKey.set(k),
      error: () => this.answerKey.set(null),
    });
  }

  protected gradeNow(): void {
    this.grading.set(true);
    this.errorMessage.set(null);

    this.gradingService.gradeSubmission(this.submissionId).subscribe({
      next: (result) => {
        this.onReport(result);
        this.notGraded.set(false);
        this.grading.set(false);
      },
      error: () => {
        this.grading.set(false);
        this.errorMessage.set(
          'Grading failed — the configured LLM providers may be rate-limited. Try again shortly.',
        );
      },
    });
  }

  protected readonly isReviewed = computed(() => !!this.result()?.reviewed_at);

  /** Sends whatever point overrides are currently staged, bakes them into the
   * stored result, and marks the report reviewed. */
  protected confirmPaper(): void {
    this.confirming.set(true);
    this.confirmError.set(null);

    this.gradingService.confirmReport(this.submissionId, this.overrides()).subscribe({
      next: (result) => {
        this.onReport(result);
        this.confirming.set(false);
      },
      error: () => {
        this.confirming.set(false);
        this.confirmError.set('Failed to confirm this paper. Try again.');
      },
    });
  }

  // ---------------------------------------------------------------- scoring

  protected awarded(grade: QuestionGrade): number {
    const override = this.overrides()[grade.question_id];
    return override === undefined ? grade.points_awarded : override;
  }

  protected isEdited(grade: QuestionGrade): boolean {
    return this.overrides()[grade.question_id] !== undefined;
  }

  protected bump(grade: QuestionGrade, delta: number): void {
    const next = Math.min(grade.points_possible, Math.max(0, this.awarded(grade) + delta));
    this.overrides.update((o) => ({ ...o, [grade.question_id]: next }));
  }

  protected clearOverride(grade: QuestionGrade): void {
    this.overrides.update((o) => {
      const next = { ...o };
      delete next[grade.question_id];
      return next;
    });
  }

  protected readonly editCount = computed(() => Object.keys(this.overrides()).length);

  protected readonly awardedTotal = computed(() => {
    const report = this.result();
    if (!report) return 0;
    return report.question_grades.reduce((sum, g) => sum + this.awarded(g), 0);
  });

  protected readonly possibleTotal = computed(() => this.result()?.total_points_possible ?? 0);

  protected readonly percent = computed(() => {
    const total = this.possibleTotal();
    return total === 0 ? 0 : Math.round((this.awardedTotal() / total) * 100);
  });

  // ------------------------------------------------------------- confidence

  /** MCQs are matched exactly; anything a model judged is open to question. */
  protected isMachineJudged(grade: QuestionGrade): boolean {
    return grade.graded_by !== 'mcq';
  }

  protected flagOf(grade: QuestionGrade): Flag {
    if (this.hasNumberingMismatch(grade)) return 'numbering';
    if (!this.isMachineJudged(grade)) return null;
    const points = this.awarded(grade);
    if (points > 0 && points < grade.points_possible) return 'partial';
    return null;
  }

  protected flagLabel(grade: QuestionGrade): string {
    const flag = this.flagOf(grade);
    if (flag === 'numbering') return 'page says ' + grade.detected_label;
    if (flag === 'partial') return 'partial credit';
    return '';
  }

  private hasNumberingMismatch(grade: QuestionGrade): boolean {
    if (!grade.detected_label) return false;
    const detected = grade.detected_label.match(/\d+/)?.[0];
    const matched = grade.question_id.match(/\d+/)?.[0];
    return detected !== undefined && matched !== undefined && detected !== matched;
  }

  protected readonly flaggedCount = computed(
    () => this.result()?.question_grades.filter((g) => this.flagOf(g)).length ?? 0,
  );

  protected readonly visibleGrades = computed(() => {
    const grades = this.result()?.question_grades ?? [];
    return this.flaggedOnly() ? grades.filter((g) => this.flagOf(g)) : grades;
  });

  protected toggleFlaggedOnly(): void {
    this.flaggedOnly.update((v) => !v);
  }

  // ------------------------------------------------------------- the answers

  protected kindOf(grade: QuestionGrade): string {
    return this.isMachineJudged(grade) ? 'Written' : 'Multiple choice';
  }

  protected originOf(grade: QuestionGrade): string {
    return this.isMachineJudged(grade) ? 'scored by ' + grade.graded_by : 'matched exactly';
  }

  protected studentAnswer(grade: QuestionGrade): string {
    const s = this.submission();
    if (!s) return '—';
    const mcq = s.mcq_responses.find((r) => r.question_id === grade.question_id);
    if (mcq) return mcq.selected_option;
    const text = s.text_responses.find((r) => r.question_id === grade.question_id);
    return text?.answer_text || '—';
  }

  protected keyAnswer(grade: QuestionGrade): string {
    const key = this.answerKey();
    if (!key) return '—';
    const mcq = key.mcq_answers.find((a) => a.question_id === grade.question_id);
    if (mcq) return mcq.correct_option;
    const text = key.text_answers.find((a) => a.question_id === grade.question_id);
    return text?.reference_answer || '—';
  }

  protected agreementLabel(grade: QuestionGrade): string {
    const points = this.awarded(grade);
    if (points === grade.points_possible) return 'full marks';
    if (points === 0) return 'no marks';
    return 'as scored';
  }

  /** Per-criterion outcome, used only for styling the rubric breakdown. */
  protected criterionStatus(c: CriterionGrade): 'met' | 'partial' | 'missed' {
    if (c.awarded_points >= c.max_points) return 'met';
    if (c.awarded_points <= 0) return 'missed';
    return 'partial';
  }

  protected meterClass(): string {
    const pct = this.percent();
    if (pct >= 75) return 'meter__fill meter__fill--high';
    if (pct >= 60) return 'meter__fill';
    return 'meter__fill meter__fill--low';
  }
}
