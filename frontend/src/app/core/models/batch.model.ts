import { GradeResult } from './grade-result.model';
import { Submission } from './submission.model';

export interface Batch {
  id: string;
  answer_key_id: string;
  created_at: string;
}

export interface BatchRow {
  submission: Submission;
  /** Null until this paper has been graded. */
  result: GradeResult | null;
}

export interface BatchDetail {
  batch: Batch;
  rows: BatchRow[];
}
