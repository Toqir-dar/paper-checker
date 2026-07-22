export interface QuestionGrade {
  question_id: string;
  points_awarded: number;
  points_possible: number;
  feedback: string;
  graded_by: string; // "mcq" | "groq:<model>" | "gemini:<model>"
}

export interface GradeResult {
  id: string;
  submission_id: string;
  answer_key_id: string;
  question_grades: QuestionGrade[];
  total_points_awarded: number;
  total_points_possible: number;
}
