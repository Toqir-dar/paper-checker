import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { SubmissionService } from '../../../core/services/submission.service';

@Component({
  selector: 'app-submission-upload',
  imports: [RouterLink, FormsModule],
  templateUrl: './submission-upload.html',
  styleUrl: './submission-upload.css',
})
export class SubmissionUpload {
  private readonly route = inject(ActivatedRoute);
  private readonly submissionService = inject(SubmissionService);
  private readonly router = inject(Router);

  protected readonly answerKeyId = this.route.snapshot.paramMap.get('answerKeyId')!;

  protected studentName = '';
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
    if (!this.studentName.trim()) {
      this.errorMessage.set('Enter the student name.');
      return;
    }
    if (!file) {
      this.errorMessage.set('Choose a scanned PDF or photo of the answer sheet first.');
      return;
    }

    this.uploading.set(true);
    this.errorMessage.set(null);

    this.submissionService
      .uploadFile(this.answerKeyId, file, { studentName: this.studentName.trim() })
      .subscribe({
        next: () => this.router.navigate(['/answer-keys', this.answerKeyId, 'submissions']),
        error: (err) => {
          this.uploading.set(false);
          this.errorMessage.set(
            err.status === 503
              ? 'The vision model is currently rate-limited across all configured providers. Try again shortly.'
              : 'Failed to process the file. Make sure it clearly shows the answers, then try again.',
          );
        },
      });
  }
}
