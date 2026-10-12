from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.wizard.schema import WizardTemplateSeed

BASELINE_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "baseline_fr.yaml"


def _read_template_seed(path: Path) -> WizardTemplateSeed:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return WizardTemplateSeed.model_validate(payload)


@lru_cache(maxsize=1)
def load_baseline_template_seed() -> WizardTemplateSeed:
    return _read_template_seed(BASELINE_TEMPLATE_PATH)


def validate_baseline_template() -> None:
    load_baseline_template_seed()


def clear_template_cache() -> None:
    load_baseline_template_seed.cache_clear()
