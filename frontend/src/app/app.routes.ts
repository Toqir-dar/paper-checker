import { Routes } from '@angular/router';
import { Dashboard } from './features/dashboard/dashboard';
import { AnswerKeyList } from './features/answer-keys/answer-key-list/answer-key-list';
import { AnswerKeyForm } from './features/answer-keys/answer-key-form/answer-key-form';
import { AnswerKeyUpload } from './features/answer-keys/answer-key-upload/answer-key-upload';
import { SubmissionList } from './features/submissions/submission-list/submission-list';
import { SubmissionForm } from './features/submissions/submission-form/submission-form';
import { SubmissionUpload } from './features/submissions/submission-upload/submission-upload';
import { GradeReport } from './features/reports/grade-report/grade-report';
import { BatchUpload } from './features/batches/batch-upload/batch-upload';
import { BatchResults } from './features/batches/batch-results/batch-results';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'today' },
  { path: 'today', component: Dashboard },
  { path: 'answer-keys', component: AnswerKeyList },
  { path: 'answer-keys/new', component: AnswerKeyForm },
  { path: 'answer-keys/upload', component: AnswerKeyUpload },
  { path: 'answer-keys/:answerKeyId/edit', component: AnswerKeyForm },
  { path: 'answer-keys/:answerKeyId/submissions', component: SubmissionList },
  { path: 'answer-keys/:answerKeyId/submissions/new', component: SubmissionForm },
  { path: 'answer-keys/:answerKeyId/submissions/upload', component: SubmissionUpload },
  { path: 'answer-keys/:answerKeyId/batches/new', component: BatchUpload },
  { path: 'batches/:batchId', component: BatchResults },
  { path: 'submissions/:submissionId/report', component: GradeReport },
  { path: '**', redirectTo: 'today' },
];
