"""Seleção determinística da regra de responsabilidade vigente."""

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.models.classification import RouteDecision, RoutingRule
from app.models.reports import ReportCategory


@lru_cache(maxsize=1)
def _load_rules() -> tuple[str, tuple[RoutingRule, ...]]:
    seed_path = Path(__file__).resolve().parents[1] / "seeds" / "routing_matrix.json"
    with seed_path.open(encoding="utf-8") as seed_file:
        data = json.load(seed_file)
    territory_id = data["territory_id"]
    rules = tuple(RoutingRule.model_validate(rule) for rule in data["rules"])
    return territory_id, rules


class RoutingService:
    def __init__(self, *, clock=lambda: datetime.now(timezone.utc)) -> None:
        self._clock = clock

    def list_agencies(self) -> list[tuple[str, str]]:
        """Órgãos distintos presentes na matriz vigente, ordenados por nome."""
        territory_id, rules = _load_rules()
        now = self._clock()
        agencies = {
            rule.agency_id: rule.agency_name
            for rule in rules
            if rule.territory_id == territory_id
            and datetime.fromisoformat(rule.valid_from.replace("Z", "+00:00")) <= now
            and (
                rule.valid_to is None
                or now
                < datetime.fromisoformat(rule.valid_to.replace("Z", "+00:00"))
            )
        }
        return sorted(agencies.items(), key=lambda item: item[1])

    def agency_email(self, agency_id: str) -> str | None:
        """E-mail de contato do órgão na matriz vigente (para o aviso de encaminhamento)."""
        _, rules = _load_rules()
        return next(
            (rule.agency_email for rule in rules if rule.agency_id == agency_id),
            None,
        )

    def find_rule(
        self,
        category: ReportCategory,
        subcategory: str | None,
    ) -> RouteDecision | None:
        territory_id, rules = _load_rules()
        now = self._clock()
        candidates = [
            rule
            for rule in rules
            if rule.territory_id == territory_id
            and rule.category == category
            and (rule.subcategory is None or rule.subcategory == subcategory)
            and datetime.fromisoformat(rule.valid_from.replace("Z", "+00:00")) <= now
            and (
                rule.valid_to is None
                or now
                < datetime.fromisoformat(rule.valid_to.replace("Z", "+00:00"))
            )
        ]
        if not candidates:
            return None
        rule = max(
            candidates,
            key=lambda candidate: (
                candidate.subcategory is not None,
                candidate.version,
            ),
        )
        return RouteDecision(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            territory_id=rule.territory_id,
            agency_id=rule.agency_id,
            agency_name=rule.agency_name,
            deadline_hours=rule.deadline_hours,
            agency_email=rule.agency_email,
        )
