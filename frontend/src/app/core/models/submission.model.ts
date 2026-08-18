export interface McqResponse {
  question_id: string;
  selected_option: string;
}

export interface TextResponse {
  question_id: string;
  answer_text: string;
}

export interface Submission {
  id: string;
  answer_key_id: string;
  student_name: string;
  /** Read off the page by the vision model; empty if none was visible. */
  roll_number: string;
  /** Set only for submissions created through the batch-upload flow. */
  batch_id: string | null;
  mcq_responses: McqResponse[];
  text_responses: TextResponse[];
}

export type SubmissionDraft = Omit<Submission, 'id'>;
