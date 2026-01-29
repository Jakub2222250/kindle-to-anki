"""Loader for model definitions from YAML configuration."""

import sys
from pathlib import Path
from typing import List

import yaml

from .modelspec import ModelSpec


def get_models_config_path() -> Path:
    """Get models.yaml path, handling both development and PyInstaller frozen builds."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "data" / "config" / "models.yaml"
    else:
        return Path(__file__).parent.parent.parent.parent.parent / "data" / "config" / "models.yaml"


def load_models_from_yaml() -> List[ModelSpec]:
    """Load all model definitions from models.yaml."""
    config_path = get_models_config_path()

    if not config_path.exists():
        raise FileNotFoundError(f"Models config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    models = []
    for entry in data.get("models", []):
        model = ModelSpec(
            id=entry["id"],
            platform_id=entry["platform_id"],
            family=entry["family"],
            quality_tier=entry["quality_tier"],
            encoding=entry["encoding"],
            supports_json=entry.get("supports_json"),
            input_token_cost_per_1m=entry.get("input_token_cost_per_1m"),
            output_token_cost_per_1m=entry.get("output_token_cost_per_1m"),
            typical_latency_ms=entry.get("typical_latency_ms"),
            notes=entry.get("notes"),
            rpm_limit=entry.get("rpm_limit"),
            tpm_limit=entry.get("tpm_limit"),
            rpd_limit=entry.get("rpd_limit"),
        )
        models.append(model)

    return models
