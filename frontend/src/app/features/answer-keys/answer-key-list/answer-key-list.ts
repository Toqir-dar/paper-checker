import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { AnswerKeyService } from '../../../core/services/answer-key.service';

@Component({
  selector: 'app-answer-key-list',
  imports: [RouterLink],
  templateUrl: './answer-key-list.html',
  styleUrl: './answer-key-list.css',
})
export class AnswerKeyList {
  private readonly answerKeyService = inject(AnswerKeyService);

  protected readonly answerKeys = toSignal(this.answerKeyService.list(), {
    initialValue: [],
  });
}
