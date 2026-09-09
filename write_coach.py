from pathlib import Path

coach_service = """\""\"
Coach Agent Service - Sprint 5.

Provides a 3-step coaching pipeline:
  Step 1: Skill-gap diagnostic analysis & learning roadmap
  Step 2: Curated question bank (technical, behavioral, gap-probing)
  Step 3: Rubric-based answer evaluation & interview readiness scoring

Uses Gemini as the primary LLM with a high-fidelity rule-based fallback.
\""\"

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.coach import (
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    CoachQuestionBankRequest,
    FullCoachingSessionResponse,
    InterviewQuestion,
    QuestionBank,
    SkillGapItem,
    SkillGapReport,
)
"""
Path("write_coach.py").write_text("# placeholder", encoding="utf-8")
print("placeholder ok")
