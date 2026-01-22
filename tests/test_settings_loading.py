"""
Test settings loading from .env file.

This test verifies that all settings sections load correctly
from the .env file and that all fields are properly typed.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

# 1) Import api.dependencies so dotenv loads exactly once (canonical location).
import api.dependencies  # noqa: F401

from core.settings import get_app_settings


def _parse_env_keys(env_path: Path) -> list[str]:
    text = env_path.read_text(encoding="utf-8", errors="replace")
    keys: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[len("export ") :].strip()
        if "=" not in s:
            continue
        k, _ = s.split("=", 1)
        k = k.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
            continue
        keys.append(k)
    # de-duplicate while preserving order
    seen = set()
    out: list[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def _collect_alias_map(model) -> dict[str, str]:
    """
    Return map: ENV_ALIAS -> field_name for a Pydantic model.
    """
    alias_map: dict[str, str] = {}
    for field_name, field in type(model).model_fields.items():
        alias = field.alias
        if alias:
            alias_map[alias] = field_name
    return alias_map


def test_every_env_key_is_mapped_and_non_none():
    """
    PHASE 8 requirements:
    1) Import api.dependencies (dotenv loads once)
    2) Call get_app_settings()
    3) For every env variable:
       - ensure that settings.<module>.<field> is not None
       - ensure field alias matches env key
    4) Ensure no ImportError or ValidationError occurs.
    """
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    keys = _parse_env_keys(env_path)

    settings = get_app_settings()

    # Collect alias maps for each module + nested integrations
    modules = {
        "amazon": settings.amazon,
        "odoo": settings.odoo,
        "noon": settings.noon,
        "warehouse": settings.warehouse,
        "bank": settings.bank,
        "telegram": settings.integrations.telegram,
        "whatsapp": settings.integrations.whatsapp,
        "slack": settings.integrations.slack,
        "notion": settings.integrations.notion,
    }

    alias_to_locator: dict[str, tuple[str, str]] = {}
    for module_name, model in modules.items():
        for alias, field_name in _collect_alias_map(model).items():
            if alias in alias_to_locator:
                pytest.fail(f"Duplicate env alias mapped twice: {alias}")
            alias_to_locator[alias] = (module_name, field_name)

    missing = [k for k in keys if k not in alias_to_locator]
    assert not missing, f"Unmapped env keys: {missing}"

    for env_key in keys:
        module_name, field_name = alias_to_locator[env_key]
        model = modules[module_name]

        # Ensure alias matches env key
        assert type(model).model_fields[field_name].alias == env_key

        # Ensure field is not None
        assert getattr(model, field_name) is not None
