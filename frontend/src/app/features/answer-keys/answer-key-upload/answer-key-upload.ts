import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AnswerKeyService } from '../../../core/services/answer-key.service';
import { Subject } from '../../../core/models/subject.model';
import { SubjectService } from '../../../core/services/subject.service';

@Component({
  selector: 'app-answer-key-upload',
  imports: [RouterLink],
  templateUrl: './answer-key-upload.html',
  styleUrl: './answer-key-upload.css',
})
export class AnswerKeyUpload {
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly router = inject(Router);
  private readonly subjectService = inject(SubjectService);

  protected readonly selectedFile = signal<File | null>(null);
  protected readonly uploading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly subjects = signal<Subject[]>([]);
  protected readonly subjectId = signal('');
  protected readonly newSubjectName = signal('');

  constructor() {
    this.subjectService.list().subscribe((subjects) => this.subjects.set(subjects));
  }

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile.set(input.files?.[0] ?? null);
    this.errorMessage.set(null);
  }

  protected submit(): void {
    const file = this.selectedFile();
    if (!file) {
      this.errorMessage.set('Choose a PDF, image, or Word (.docx) file first.');
      return;
    }

    this.uploading.set(true);
    this.errorMessage.set(null);

    this.answerKeyService.uploadFile(file, this.subjectId()).subscribe({
      // Land on the review/edit form, not submissions — the vision model's
      // extracted questions and points need a human check before they're
      // used to grade anything.
      next: (created) => this.router.navigate(['/answer-keys', created.id, 'edit']),
      error: (err) => {
        this.uploading.set(false);
        this.errorMessage.set(
          err.status === 503
            ? 'The vision model is currently rate-limited across all configured providers. Try again shortly.'
            : 'Failed to process the file. Make sure it clearly shows the questions and answers, then try again.',
        );
      },
    });
  }

  protected createSubject(): void {
    const name = this.newSubjectName().trim();
    if (!name) return;
    this.subjectService.create(name).subscribe({
      next: (subject) => {
        this.subjects.update((subjects) => subjects.some((item) => item.id === subject.id) ? subjects : [...subjects, subject].sort((a, b) => a.name.localeCompare(b.name)));
        this.subjectId.set(subject.id);
        this.newSubjectName.set('');
      },
      error: () => this.errorMessage.set('Could not create the subject.'),
    });
  }
}
