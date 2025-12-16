"""High-level facade that wires together AI content generator mixins."""

from __future__ import annotations

from .ai_generator_base import BaseAIContentGenerator, logger
from .ai_generator_content import ContentGenerationMixin, StoryGenerationMixin
from .ai_generator_media import MediaGenerationMixin, merge_video_prompt_with_additional


class AIContentGenerator(
    StoryGenerationMixin,
    ContentGenerationMixin,
    MediaGenerationMixin,
    BaseAIContentGenerator,
):
    """AI-генератор контента для социальных сетей."""


__all__ = ["AIContentGenerator", "merge_video_prompt_with_additional", "logger"]
