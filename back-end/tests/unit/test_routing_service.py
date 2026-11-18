import unittest
from datetime import datetime, timezone

from app.models.taxonomy import ReportCategory
from app.services.routing_service import RoutingService


class RoutingServiceTests(unittest.TestCase):
    def test_specific_subcategory_rule_precedes_category_default(self) -> None:
        routing = RoutingService(
            clock=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc)
        )

        route = routing.find_rule(
            ReportCategory.URBAN_RISK,
            "esgoto_vazamento",
        )

        self.assertIsNotNone(route)
        self.assertEqual(route.rule_id, "esgoto-saneamento")
        self.assertEqual(route.agency_id, "saneamento-demo")

    def test_other_urban_risk_uses_category_default(self) -> None:
        routing = RoutingService(
            clock=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc)
        )

        route = routing.find_rule(ReportCategory.URBAN_RISK, "buraco_via")

        self.assertIsNotNone(route)
        self.assertEqual(route.rule_id, "risco-urbano-geral")
        self.assertEqual(route.agency_id, "prefeitura-demo-zeladoria")

    def test_unclassified_report_has_no_route_and_goes_to_moderation(self) -> None:
        routing = RoutingService(
            clock=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc)
        )

        route = routing.find_rule(ReportCategory.TO_CLASSIFY, "a_classificar")

        self.assertIsNone(route)


if __name__ == "__main__":
    unittest.main()
