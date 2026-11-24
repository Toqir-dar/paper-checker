from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class LshPair(BaseModel):
    question_id: str
    submission_id_a: str
    submission_id_b: str
    roll_a: str = ""
    roll_b: str = ""
    jaccard: float
    cosine: float | None = None
    lsh_candidate: bool = True


class LshQuestionMetrics(BaseModel):
    question_id: str
    brute_similar_pairs: int
    lsh_candidates: int
    false_positives: int
    false_negatives: int
    threshold: float


class ClusterAssignment(BaseModel):
    submission_id: str
    roll_number: str = ""
    cluster_id: int


class ElbowPoint(BaseModel):
    k: int
    inertia: float


class AssociationRuleOut(BaseModel):
    antecedent: list[str]
    consequent: list[str]
    support: float
    confidence: float
    lift: float


class ItemsetAnalytics(BaseModel):
    method: str
    frequent_itemsets: list[dict[str, Any]] = Field(default_factory=list)
    rules: list[AssociationRuleOut] = Field(default_factory=list)


class PageRankScore(BaseModel):
    submission_id: str
    roll_number: str = ""
    score: float


class AuditSample(BaseModel):
    submission_id: str
    question_id: str
    roll_number: str = ""
    answer_text: str


class CorrelationOut(BaseModel):
    feature_a: str
    feature_b: str
    pearson_r: float
    p_value_approx: float
    significant_raw: bool
    significant_bonferroni: bool


class EdaOut(BaseModel):
    n_students: int
    mean_score: float | None = None
    std_score: float | None = None
    correlations: list[CorrelationOut] = Field(default_factory=list)


class RecommendationOut(BaseModel):
    question_id: str
    reason: str
    score: float


class RecommenderEvalOut(BaseModel):
    rmse: float | None = None
    precision_at_k: float | None = None
    k: int = 3
    held_out: int = 0


class PdfChunkMeta(BaseModel):
    page_index: int
    byte_size: int


class BatchAnalytics(BaseModel):
    """Stored result of a product DM analytics job for one batch."""

    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    batch_id: str
    answer_key_id: str
    lsh_pairs: list[LshPair] = Field(default_factory=list)
    lsh_metrics: list[LshQuestionMetrics] = Field(default_factory=list)
    clusters: list[ClusterAssignment] = Field(default_factory=list)
    elbow: list[ElbowPoint] = Field(default_factory=list)
    chosen_k: int = 0
    itemsets: ItemsetAnalytics = Field(default_factory=lambda: ItemsetAnalytics(method="apriori"))
    pagerank: list[PageRankScore] = Field(default_factory=list)
    audit_samples: list[AuditSample] = Field(default_factory=list)
    recommendations: dict[str, list[RecommendationOut]] = Field(default_factory=dict)
    recommender_eval: RecommenderEvalOut | None = None
    eda: EdaOut | None = None
    pdf_chunk_notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
