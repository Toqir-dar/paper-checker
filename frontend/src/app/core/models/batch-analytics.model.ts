export interface LshPair {
  question_id: string;
  submission_id_a: string;
  submission_id_b: string;
  roll_a: string;
  roll_b: string;
  jaccard: number;
  cosine: number | null;
  lsh_candidate: boolean;
}

export interface LshQuestionMetrics {
  question_id: string;
  brute_similar_pairs: number;
  lsh_candidates: number;
  false_positives: number;
  false_negatives: number;
  threshold: number;
}

export interface ClusterAssignment {
  submission_id: string;
  roll_number: string;
  cluster_id: number;
}

export interface ElbowPoint {
  k: number;
  inertia: number;
}

export interface AssociationRule {
  antecedent: string[];
  consequent: string[];
  support: number;
  confidence: number;
  lift: number;
}

export interface ItemsetAnalytics {
  method: string;
  frequent_itemsets: { items: string[]; support: number; count: number }[];
  rules: AssociationRule[];
}

export interface PageRankScore {
  submission_id: string;
  roll_number: string;
  score: number;
}

export interface AuditSample {
  submission_id: string;
  question_id: string;
  roll_number: string;
  answer_text: string;
}

export interface CorrelationOut {
  feature_a: string;
  feature_b: string;
  pearson_r: number;
  p_value_approx: number;
  significant_raw: boolean;
  significant_bonferroni: boolean;
}

export interface EdaOut {
  n_students: number;
  mean_score: number | null;
  std_score: number | null;
  correlations: CorrelationOut[];
}

export interface BatchAnalytics {
  id: string;
  batch_id: string;
  answer_key_id: string;
  lsh_pairs: LshPair[];
  lsh_metrics: LshQuestionMetrics[];
  clusters: ClusterAssignment[];
  elbow: ElbowPoint[];
  chosen_k: number;
  itemsets: ItemsetAnalytics;
  pagerank: PageRankScore[];
  audit_samples: AuditSample[];
  recommendations: Record<string, { question_id: string; reason: string; score: number }[]>;
  recommender_eval: {
    rmse: number | null;
    precision_at_k: number | null;
    k: number;
    held_out: number;
  } | null;
  eda: EdaOut | null;
  metrics: Record<string, unknown>;
  warnings: string[];
  created_at: string;
}
