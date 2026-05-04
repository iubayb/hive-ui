"""org_guard.py — Absolute GitHub org isolation guard.

CRITICAL INVARIANT: Hive must NEVER write to hatcher/* or bolder/* repos.
These are production codebases. Violation is a job-ending event.

This file is intentionally minimal (stdlib only: os, re).
The forbidden org names below are HARDCODED — never read from env or config.
DO NOT modify this file without explicit human approval.
DO NOT make _FORBIDDEN configurable. Ever.
"""
import os
import re

# Hard-coded. Not configurable. Not overridable. Do not change.
# Forbidden org names: "hatcher" and "bolder" — these are live production repos.
_FORBIDDEN = re.compile(r"^(hatcher|bolder)/", re.IGNORECASE)


def assert_hive_repo(repo: str, operation: str = "write") -> None:
    """
    MUST be called as the first statement of every GitHub write function.
    Raises RuntimeError immediately on any violation — no exceptions, no retries,
    no logging-and-continuing.

    Two-layer check:
      Layer 1: hard-coded forbidden pattern (hatcher/*, bolder/*) — always active,
               cannot be disabled by any env var or config.
      Layer 2: exact match with HIVE_GITHUB_REPO env var — enforced when set,
               fail-closed (blocks all writes if repo does not match exactly).
    """
    # Layer 1: absolute forbidden — hardcoded, permanent
    if _FORBIDDEN.match(repo):
        raise RuntimeError(
            f"[ORG-VIOLATION] CRITICAL: blocked '{operation}' to forbidden repo "
            f"'{repo}'. hatcher/* and bolder/* are production repos — hive must "
            f"never write to them. This constraint is hardcoded in org_guard.py "
            f"and cannot be overridden."
        )

    # Layer 2: must match configured hive repo exactly (fail-closed when set)
    configured = os.environ.get("HIVE_GITHUB_REPO", "").strip()
    if configured and repo != configured:
        raise RuntimeError(
            f"[ORG-VIOLATION] CRITICAL: blocked '{operation}' to '{repo}'. "
            f"Configured hive repo is HIVE_GITHUB_REPO='{configured}'. "
            f"Write target must match exactly."
        )
