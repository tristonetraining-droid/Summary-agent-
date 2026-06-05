"""Stage 4: Reduce — tone enforcement + consistency checks."""
from __future__ import annotations

import logging

from . import config, llm
from .models import CIMSummary
from .prompts.sections import SYNTHESIZER

log = logging.getLogger(__name__)


def synthesize(summary: CIMSummary) -> CIMSummary:
    tone = llm.load_tone()
    system = f"{tone}\n\n--- TASK ---\n{SYNTHESIZER}"
    user = "Current draft CIMSummary JSON:\n\n" + summary.model_dump_json(indent=2)
    try:
        corrected = llm.call_structured(
            model=config.CLAUDE_MODEL_SONNET,
            system=system,
            user=user,
            schema=CIMSummary,
            max_tokens=8000,
            temperature=0.1,
        )
        return _postvalidate(corrected)
    except Exception as e:
        log.exception("synthesizer failed: %s — returning draft", e)
        return _postvalidate(summary)


def _postvalidate(s: CIMSummary) -> CIMSummary:
    # S&U balance check
    su = s.sources_and_uses
    if su.sources_total is not None and su.uses_total is not None:
        su.balanced = abs(su.sources_total - su.uses_total) <= 0.5
        if not su.balanced and not su.note:
            su.note = f"Sources/Uses mismatch: ${su.sources_total:.1f}M vs ${su.uses_total:.1f}M (CIM)."
    # Clip bullets to 5
    s.deal_overview.bullets = s.deal_overview.bullets[:5]
    s.highlights_and_risks.highlights = s.highlights_and_risks.highlights[:5]
    s.highlights_and_risks.risks = s.highlights_and_risks.risks[:5]
    s.sponsor_value_creation.bullets = s.sponsor_value_creation.bullets[:6]
    return s
