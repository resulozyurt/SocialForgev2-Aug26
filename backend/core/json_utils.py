"""
core/json_utils.py
Robust parsing of JSON returned by LLMs.

LLMs occasionally emit *almost* valid JSON — wrapped in ```json fences, with a
sentence of preamble, with trailing commas, or (most commonly) with an
unescaped double quote inside a string value. This helper recovers from all of
those instead of throwing, so a single bad character doesn't cost us a whole
generated post.

Resolution order:
  1. Parse as-is.
  2. Extract the outermost {...} block (strips fences / prose) and parse.
  3. Repair with json_repair (fixes unescaped quotes, trailing commas, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_ai_json(content: str) -> Any:
    """Parse JSON from an LLM response, repairing it if necessary.

    Returns the parsed object (usually a dict). Raises ValueError only if even
    repair fails.
    """
    # 1) Straight parse.
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2) Extract the outermost {...} block, dropping code fences / prose.
    match = re.search(r"\{.*\}", content, re.DOTALL)
    candidate = match.group() if match else content
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 3) Repair (handles unescaped inner quotes, trailing commas, etc.).
    try:
        from json_repair import repair_json

        repaired = repair_json(candidate, return_objects=True)
        if isinstance(repaired, (dict, list)) and repaired:
            logger.info("Recovered AI JSON via json_repair.")
            return repaired
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"json_repair could not recover the response: {exc}")

    raise ValueError(f"AI response was not valid JSON: {content[:200]}")