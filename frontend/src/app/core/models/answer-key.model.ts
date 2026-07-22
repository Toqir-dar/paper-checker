export interface McqAnswer {
  question_id: string;
  correct_option: string;
  points: number;
}

export interface RubricCriterion {
  description: string;
  max_points: number;
}

export interface TextAnswer {
  question_id: string;
  reference_answer: string;
  rubric: RubricCriterion[];
}

export interface AnswerKey {
  id: string;
  title: string;
  mcq_answers: McqAnswer[];
  text_answers: TextAnswer[];
}

export type AnswerKeyDraft = Omit<AnswerKey, 'id'>;
