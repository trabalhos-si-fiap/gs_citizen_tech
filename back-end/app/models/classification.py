"""Modelos de classificação e roteamento."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.taxonomy import ReportCategory, load_taxonomy, validate_taxonomy


class ClassificationInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str | None
    user_category: ReportCategory | None


class ClassificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: ReportCategory
    subcategory: str | None
    urgency: Literal["baixa", "media", "alta"] | None
    confidence: float = Field(ge=0, le=1)
    immediate_risk: bool | None
    model: str
    escalated: bool = False
    source: Literal["ai", "user", "none"]

    @model_validator(mode="after")
    def validate_category_pair(self) -> "ClassificationResult":
        validate_taxonomy(self.category, self.subcategory)
        return self


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["confirm", "correct"]
    category: ReportCategory | None = None
    subcategory: str | None = None

    @model_validator(mode="after")
    def validate_action(self) -> "TriageRequest":
        if self.action == "correct":
            if self.category is None:
                raise ValueError("Categoria obrigatória para corrigir a triagem.")
            validate_taxonomy(self.category, self.subcategory)
        elif self.category is not None or self.subcategory is not None:
            raise ValueError("Confirmação não aceita categoria ou subcategoria.")
        return self


class RoutingRule(BaseModel):
    rule_id: str
    version: int = Field(ge=1)
    territory_id: str
    category: ReportCategory
    subcategory: str | None = None
    agency_id: str
    agency_name: str
    agency_email: str | None = None
    deadline_hours: int = Field(gt=0)
    valid_from: str
    valid_to: str | None = None

    @model_validator(mode="after")
    def validate_rule_taxonomy(self) -> "RoutingRule":
        validate_taxonomy(self.category, self.subcategory)
        return self


class RouteDecision(BaseModel):
    rule_id: str
    rule_version: int
    territory_id: str
    agency_id: str
    agency_name: str
    deadline_hours: int
    agency_email: str | None = None
