from __future__ import annotations

import unittest

from api_atlas.clustering import auth_burden, integration_archetype, readiness_cohort


def record(
    *,
    category: str = "CRM and Sales",
    verdict: str = "build_now",
    access: str = "free_self_serve",
    methods: list[str] | None = None,
    review: bool = False,
) -> dict:
    return {
        "category": category,
        "verdict": {"status": verdict},
        "access": {"level": access},
        "auth": {"methods": methods or ["oauth2"]},
        "quality": {"human_review_required": review},
    }


class ClusteringTests(unittest.TestCase):
    def test_categories_can_share_an_archetype(self) -> None:
        crm = record(category="CRM and Sales")
        support = record(category="Support and Helpdesk")
        self.assertEqual(integration_archetype(crm), "record_systems")
        self.assertEqual(integration_archetype(support), "record_systems")

    def test_human_review_overrides_build_queue(self) -> None:
        self.assertEqual(
            readiness_cohort(record(review=True)), "human_verification"
        )

    def test_partner_gate_routes_to_outreach(self) -> None:
        self.assertEqual(
            readiness_cohort(record(access="partner_gated")),
            "partnership_outreach",
        )

    def test_simple_keys_have_low_auth_burden(self) -> None:
        self.assertEqual(
            auth_burden(record(methods=["api_key"])),
            "low",
        )


if __name__ == "__main__":
    unittest.main()
