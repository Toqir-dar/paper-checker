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
import { Auth } from './features/auth/auth';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'today' },
  { path: 'login', component: Auth, data: { mode: 'login' } },
  { path: 'signup', component: Auth, data: { mode: 'signup' } },
  { path: 'today', component: Dashboard, canActivate: [authGuard] },
  { path: 'answer-keys', component: AnswerKeyList, canActivate: [authGuard] },
  { path: 'answer-keys/new', component: AnswerKeyForm, canActivate: [authGuard] },
  { path: 'answer-keys/upload', component: AnswerKeyUpload, canActivate: [authGuard] },
  { path: 'answer-keys/:answerKeyId/edit', component: AnswerKeyForm, canActivate: [authGuard] },
  { path: 'answer-keys/:answerKeyId/submissions', component: SubmissionList, canActivate: [authGuard] },
  { path: 'answer-keys/:answerKeyId/submissions/new', component: SubmissionForm, canActivate: [authGuard] },
  { path: 'answer-keys/:answerKeyId/submissions/upload', component: SubmissionUpload, canActivate: [authGuard] },
  { path: 'answer-keys/:answerKeyId/batches/new', component: BatchUpload, canActivate: [authGuard] },
  { path: 'batches/:batchId', component: BatchResults, canActivate: [authGuard] },
  { path: 'submissions/:submissionId/report', component: GradeReport, canActivate: [authGuard] },
  { path: '**', redirectTo: 'today' },
];
