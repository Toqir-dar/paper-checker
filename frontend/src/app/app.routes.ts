import { Routes } from '@angular/router';
import { AnswerKeyList } from './features/answer-keys/answer-key-list/answer-key-list';
import { AnswerKeyForm } from './features/answer-keys/answer-key-form/answer-key-form';
import { AnswerKeyUpload } from './features/answer-keys/answer-key-upload/answer-key-upload';
import { SubmissionList } from './features/submissions/submission-list/submission-list';
import { SubmissionForm } from './features/submissions/submission-form/submission-form';
import { SubmissionUpload } from './features/submissions/submission-upload/submission-upload';
import { GradeReport } from './features/reports/grade-report/grade-report';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'answer-keys' },
  { path: 'answer-keys', component: AnswerKeyList },
  { path: 'answer-keys/new', component: AnswerKeyForm },
  { path: 'answer-keys/upload', component: AnswerKeyUpload },
  { path: 'answer-keys/:answerKeyId/submissions', component: SubmissionList },
  { path: 'answer-keys/:answerKeyId/submissions/new', component: SubmissionForm },
  { path: 'answer-keys/:answerKeyId/submissions/upload', component: SubmissionUpload },
  { path: 'submissions/:submissionId/report', component: GradeReport },
  { path: '**', redirectTo: 'answer-keys' },
];
