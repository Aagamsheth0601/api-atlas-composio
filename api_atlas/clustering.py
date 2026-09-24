"""Deterministic portfolio clustering for researched app records.

The agent researches facts. These rules turn those facts into stable Product Ops
cohorts, so a rerun cannot silently redefine what "ready" or "gated" means.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


CATEGORY_ARCHETYPES = {
    "CRM and Sales": "record_systems",
    "Support and Helpdesk": "record_systems",
    "Communications and Messaging": "communication_channels",
    "Marketing, Ads, Email and Social": "growth_channels",
    "Ecommerce": "transaction_rails",
    "Data, SEO and Scraping": "data_providers",
    "Developer, Infra and Data platforms": "control_planes",
    "Productivity and Project Management": "record_systems",
    "Finance and Fintech": "transaction_rails",
    "AI, Research and Media-native": "content_processors",
}


def integration_archetype(record: dict[str, Any]) -> str:
    """Group market categories by the agent interaction they imply."""

    return CATEGORY_ARCHETYPES.get(record["category"], "uncategorized")


def readiness_cohort(record: dict[str, Any]) -> str:
    """Convert evidence-backed facts into an actionable Composio queue."""

    verdict = record["verdict"]["status"]
    access = record["access"]["level"]
    review = record["quality"]["human_review_required"]

    if verdict in {"blocked", "unclear"}:
        return "blocked_or_unclear"
    if verdict == "outreach" or access == "partner_gated":
        return "partnership_outreach"
    if review:
        return "human_verification"
    if verdict == "build_now" and access in {
        "free_self_serve",
        "trial_self_serve",
        "paid_self_serve",
    }:
        return "build_now"
    return "build_with_constraints"


def auth_burden(record: dict[str, Any]) -> str:
    """Estimate implementation burden without inventing a numeric score."""

    methods = set(record["auth"]["methods"])
    access = record["access"]["level"]
    if "unknown" in methods or access == "unknown":
        return "unknown"
    if access in {"partner_gated", "admin_gated"}:
        return "high"
    if "oauth2" in methods:
        return "moderate"
    if methods <= {"api_key", "token", "basic"}:
        return "low"
    return "moderate"


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return cluster metadata separately from the researched source record."""

    return {
        "integration_archetype": integration_archetype(record),
        "readiness_cohort": readiness_cohort(record),
        "auth_burden": auth_burden(record),
    }


def cluster_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Produce chart-ready counts for the case-study page."""

    enriched = [enrich_record(record) for record in records]
    return {
        key: dict(sorted(Counter(item[key] for item in enriched).items()))
        for key in (
            "integration_archetype",
            "readiness_cohort",
            "auth_burden",
        )
    }

