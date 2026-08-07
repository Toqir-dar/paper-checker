import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AnswerKey } from '../../../core/models/answer-key.model';
import { AnswerKeyService } from '../../../core/services/answer-key.service';

@Component({
  selector: 'app-answer-key-list',
  imports: [RouterLink],
  templateUrl: './answer-key-list.html',
  styleUrl: './answer-key-list.css',
})
export class AnswerKeyList {
  private readonly answerKeyService = inject(AnswerKeyService);

  protected readonly answerKeys = signal<AnswerKey[]>([]);
  protected readonly deletingId = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  constructor() {
    this.answerKeyService.list().subscribe((keys) => this.answerKeys.set(keys));
  }

  protected delete(key: AnswerKey): void {
    const confirmed = confirm(
      `Delete "${key.title}"? This also deletes every submission and grade filed against it.`,
    );
    if (!confirmed) {
      return;
    }

    this.deletingId.set(key.id);
    this.errorMessage.set(null);
    this.answerKeyService.delete(key.id).subscribe({
      next: () => {
        this.answerKeys.update((keys) => keys.filter((k) => k.id !== key.id));
        this.deletingId.set(null);
      },
      error: () => {
        this.deletingId.set(null);
        this.errorMessage.set('Could not delete this answer key. Try again.');
      },
    });
  }
}
