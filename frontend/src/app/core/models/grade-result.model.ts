export interface CriterionGrade {
  description: string;
  max_points: number;
  awarded_points: number;
}

export interface QuestionGrade {
  question_id: string;
  question_text: string;
  detected_label: string;
  points_awarded: number;
  points_possible: number;
  feedback: string;
  graded_by: string; // "mcq" | "rubric:<model>" | "cosine_similarity"
  criteria?: CriterionGrade[];
}

export interface GradeResult {
  id: string;
  submission_id: string;
  answer_key_id: string;
  question_grades: QuestionGrade[];
  total_points_awarded: number;
  total_points_possible: number;
  warnings: string[];
  reviewed_at: string | null;
}
