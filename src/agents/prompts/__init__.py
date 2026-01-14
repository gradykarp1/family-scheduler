"""Prompt templates for Family Scheduler agents."""

from src.agents.prompts.nl_parser_prompts import (
    NL_PARSER_SYSTEM_PROMPT,
    NL_PARSER_FEW_SHOT_EXAMPLES,
    build_nl_parser_prompt,
)
from src.agents.prompts.resolution_prompts import (
    RESOLUTION_SYSTEM_PROMPT,
    RESOLUTION_FEW_SHOT_EXAMPLES,
    build_resolution_prompt,
)

__all__ = [
    "NL_PARSER_SYSTEM_PROMPT",
    "NL_PARSER_FEW_SHOT_EXAMPLES",
    "build_nl_parser_prompt",
    "RESOLUTION_SYSTEM_PROMPT",
    "RESOLUTION_FEW_SHOT_EXAMPLES",
    "build_resolution_prompt",
]
