import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AnswerKeyService } from '../../../core/services/answer-key.service';

@Component({
  selector: 'app-answer-key-upload',
  imports: [RouterLink],
  templateUrl: './answer-key-upload.html',
  styleUrl: './answer-key-upload.css',
})
export class AnswerKeyUpload {
  private readonly answerKeyService = inject(AnswerKeyService);
  private readonly router = inject(Router);

  protected readonly selectedFile = signal<File | null>(null);
  protected readonly uploading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile.set(input.files?.[0] ?? null);
    this.errorMessage.set(null);
  }

  protected submit(): void {
    const file = this.selectedFile();
    if (!file) {
      this.errorMessage.set('Choose a PDF or image file first.');
      return;
    }

    this.uploading.set(true);
    this.errorMessage.set(null);

    this.answerKeyService.uploadFile(file).subscribe({
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
}
