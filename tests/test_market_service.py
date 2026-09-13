"""Unit tests for Market Intelligence Agent service - Sprint 6."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.market import (
    DemandHeatmapRequest,
    RoleOverviewRequest,
    SalaryBand,
    SalaryInsightsRequest,
    SkillDemandRequest,
)
from app.services.market_service import (
    MarketAgent,
    _CATEGORY_CODES,
    _HOURS_PER_YEAR,
    _rule_based_heatmap_narrative,
    _rule_based_overview_narrative,
    _rule_based_salary_narrative,
    _rule_based_skills_narrative,
    aggregate_salary,
    compute_skill_demand,
    normalise_salary,
)


# ---------------------------------------------------------------------------
# normalise_salary tests
# ---------------------------------------------------------------------------

def test_normalise_salary_yearly_passthrough():
    assert normalise_salary(100_000, "YEARLY") == 100_000.0


def test_normalise_salary_hourly_conversion():
    result = normalise_salary(50.0, "HOURLY")
    assert result == round(50.0 * _HOURS_PER_YEAR, 2)


def test_normalise_salary_weekly_conversion():
    result = normalise_salary(1_000.0, "WEEKLY")
    assert result == 52_000.0


def test_normalise_salary_monthly_conversion():
    result = normalise_salary(5_000.0, "MONTHLY")
    assert result == 60_000.0


def test_normalise_salary_none_returns_none():
    assert normalise_salary(None, "YEARLY") is None


def test_normalise_salary_zero_returns_none():
    assert normalise_salary(0.0, "YEARLY") is None


def test_normalise_salary_unknown_period_treated_as_yearly():
    assert normalise_salary(80_000.0, "BIWEEKLY") == 80_000.0


# ---------------------------------------------------------------------------
# aggregate_salary tests
# ---------------------------------------------------------------------------

def test_aggregate_salary_basic():
    rows = [
        {"min_salary": 80_000, "max_salary": 120_000, "med_salary": 100_000, "pay_period": "YEARLY"},
        {"min_salary": 90_000, "max_salary": 130_000, "med_salary": 110_000, "pay_period": "YEARLY"},
    ]
    band = aggregate_salary(rows)
    assert band.sample_size > 0
    assert band.median_annual is not None
    assert band.min_annual == 80_000.0
    assert band.max_annual == 130_000.0


def test_aggregate_salary_empty_rows():
    band = aggregate_salary([])
    assert band.sample_size == 0
    assert band.median_annual is None


def test_aggregate_salary_filters_nulls():
    rows = [
        {"min_salary": None, "max_salary": None, "med_salary": None, "pay_period": "YEARLY"},
        {"min_salary": 70_000, "max_salary": None, "med_salary": None, "pay_period": "YEARLY"},
    ]
    band = aggregate_salary(rows)
    assert band.sample_size == 1
    assert band.min_annual == 70_000.0


def test_aggregate_salary_normalises_hourly():
    rows = [
        {"min_salary": 40.0, "max_salary": 60.0, "med_salary": 50.0, "pay_period": "HOURLY"},
    ]
    band = aggregate_salary(rows)
    assert band.sample_size > 0
    assert band.median_annual == round(50.0 * _HOURS_PER_YEAR, 2)


def test_aggregate_salary_sanity_bounds():
    """Values outside [5000, 2_000_000] should be filtered."""
    rows = [
        {"min_salary": 1.0, "max_salary": None, "med_salary": None, "pay_period": "YEARLY"},
        {"min_salary": 5_000_000, "max_salary": None, "med_salary": None, "pay_period": "YEARLY"},
        {"min_salary": 80_000, "max_salary": None, "med_salary": None, "pay_period": "YEARLY"},
    ]
    band = aggregate_salary(rows)
    assert band.sample_size == 1
    assert band.min_annual == 80_000.0


# ---------------------------------------------------------------------------
# compute_skill_demand tests
# ---------------------------------------------------------------------------

def test_skill_demand_counts_correctly():
    arrays = [
        ["Python", "SQL"],
        ["Python", "JavaScript"],
        ["SQL", "Docker"],
    ]
    items = compute_skill_demand(arrays, total_postings=3, top_n=5)
    python_item = next((i for i in items if i.skill == "Python"), None)
    assert python_item is not None
    assert python_item.posting_count == 2
    assert python_item.percentage == pytest.approx(66.7, rel=0.05)


def test_skill_demand_filters_category_codes():
    arrays = [["Python", "IT", "HCPR", "ENG", "JavaScript"]]
    items = compute_skill_demand(arrays, total_postings=1, top_n=10)
    skill_names = [i.skill for i in items]
    for code in ["IT", "HCPR", "ENG"]:
        assert code not in skill_names
    assert "Python" in skill_names
    assert "JavaScript" in skill_names


def test_skill_demand_trend_signal_high():
    # 3 out of 5 = 60% → "high"
    arrays = [["Python"]] * 3 + [["SQL"]] * 2
    items = compute_skill_demand(arrays, total_postings=5, top_n=1)
    assert items[0].skill == "Python"
    assert items[0].trend_signal == "high"


def test_skill_demand_trend_signal_low():
    # 1 out of 50 = 2% → "low"
    arrays = [["Python"]] + [["SQL"]] * 49
    items = compute_skill_demand(arrays, total_postings=50, top_n=10)
    python_item = next((i for i in items if i.skill == "Python"), None)
    if python_item:
        assert python_item.trend_signal == "low"


def test_skill_demand_respects_top_n():
    arrays = [[f"Skill{i}"] for i in range(20)]
    items = compute_skill_demand(arrays, total_postings=20, top_n=5)
    assert len(items) <= 5


def test_skill_demand_empty_arrays():
    items = compute_skill_demand([], total_postings=0, top_n=10)
    assert items == []


# ---------------------------------------------------------------------------
# Rule-based narrative tests
# ---------------------------------------------------------------------------

def test_rule_based_salary_narrative_with_data():
    band = SalaryBand(
        min_annual=70_000, p25_annual=85_000, median_annual=100_000,
        p75_annual=120_000, max_annual=150_000, mean_annual=102_000,
        sample_size=25,
    )
    text = _rule_based_salary_narrative("Software Engineer", band, "New York")
    assert len(text) > 50
    assert "Software Engineer" in text
    assert "100,000" in text or "median" in text.lower()


def test_rule_based_salary_narrative_insufficient_data():
    band = SalaryBand(sample_size=1)
    text = _rule_based_salary_narrative("Data Scientist", band, None)
    assert "limited" in text.lower() or "insufficient" in text.lower() or "fewer" in text.lower()


def test_rule_based_skills_narrative_with_skills():
    from app.schemas.market import SkillDemandItem
    skills = [
        SkillDemandItem(skill="Python", posting_count=40, percentage=80.0, trend_signal="high"),
        SkillDemandItem(skill="SQL", posting_count=30, percentage=60.0, trend_signal="high"),
        SkillDemandItem(skill="Docker", posting_count=15, percentage=30.0, trend_signal="high"),
    ]
    text = _rule_based_skills_narrative("Data Scientist", skills, 50)
    assert "Python" in text
    assert len(text) > 30


def test_rule_based_skills_narrative_empty():
    text = _rule_based_skills_narrative("Nurse", [], 0)
    assert len(text) > 10


def test_rule_based_heatmap_narrative():
    from app.schemas.market import LocationDemandItem
    locs = [
        LocationDemandItem(location="San Francisco, CA", posting_count=30, percentage=30.0, remote_pct=60.0),
        LocationDemandItem(location="New York, NY", posting_count=20, percentage=20.0, remote_pct=40.0),
    ]
    text = _rule_based_heatmap_narrative("Software Engineer", locs, 100)
    assert "San Francisco" in text
    assert len(text) > 30


def test_rule_based_overview_narrative():
    from app.schemas.market import SkillDemandItem
    band = SalaryBand(median_annual=110_000, sample_size=20)
    skills = [SkillDemandItem(skill="Python", posting_count=20, percentage=40.0, trend_signal="high")]
    text = _rule_based_overview_narrative("Software Engineer", 50, 45.0, band, skills)
    assert "Software Engineer" in text
    assert "Python" in text
    assert len(text) > 40


# ---------------------------------------------------------------------------
# MarketAgent class tests (no DB, no LLM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_market_agent_no_gemini_uses_fallback():
    """When gemini_key is None, narrative comes from rule-based fallback."""
    agent = MarketAgent()
    agent.gemini_key = None
    result = await agent._gemini_narrative("salary", {"role": "Engineer", "band": {}, "location": None})
    assert result == ""


@pytest.mark.asyncio
async def test_market_agent_gemini_failure_falls_back():
    """When Gemini call raises, _gemini_narrative returns empty string."""
    agent = MarketAgent()
    agent.gemini_key = "fake-key"

    with patch("httpx.AsyncClient.post", side_effect=RuntimeError("Network error")):
        result = await agent._gemini_narrative("salary", {"role": "Engineer", "band": {}, "location": None})
    assert result == ""


@pytest.mark.asyncio
async def test_market_agent_gemini_truncation_falls_back():
    """When Gemini returns a truncated fragment (<25 words), _gemini_narrative rejects it."""
    agent = MarketAgent()
    agent.gemini_key = "fake-key"

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "candidates": [
            {
                "finishReason": "MAX_TOKENS",
                "content": {
                    "parts": [{"text": "candidates.\n * Drafting: From an analytical perspective, it is critical to note"}]
                },
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=fake_resp):
        result = await agent._gemini_narrative("salary", {"role": "Engineer"})
    assert result == ""


@pytest.mark.asyncio
async def test_market_agent_gemini_cleans_drafting_artifacts():
    """When Gemini includes leading drafting labels, they are stripped from the final narrative."""
    agent = MarketAgent()
    agent.gemini_key = "fake-key"

    body_text = (
        "* Drafting: The compensation landscape for Software Engineers demonstrates significant strength. "
        "With a median salary well into six figures, qualified candidates hold strong negotiation leverage.\n\n"
        "Employers must remain competitive by offering strong equity and remote flexibility to retain top engineering talent."
    )
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": body_text}]},
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=fake_resp):
        result = await agent._gemini_narrative("salary", {"role": "Engineer"})

    assert "Drafting:" not in result
    assert result.startswith("The compensation landscape")
    assert len(result.split()) >= 25


@pytest.mark.asyncio
async def test_query_skills_arrays_extracts_from_description_and_title():
    """Verify that _query_skills_arrays extracts real skills even when skills column only has category codes."""
    agent = MarketAgent()
    mock_db = AsyncMock()

    mock_row1 = MagicMock()
    mock_row1.skills = ["IT", "ENG"]
    mock_row1.title = "Software Engineer"
    mock_row1.description = "We need an engineer experienced with Python, SQL, and Docker."

    mock_row2 = MagicMock()
    mock_row2.skills = ["IT"]
    mock_row2.title = "Frontend Developer"
    mock_row2.description = "Seeking a React and JavaScript specialist with HTML/CSS skills."

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row1, mock_row2]
    mock_db.execute = AsyncMock(return_value=mock_result)

    arrays, total = await agent._query_skills_arrays(mock_db, title_query="Engineer", location=None)

    assert total == 2
    assert len(arrays) == 2
    # Row 1 skills
    assert "Python" in arrays[0]
    assert "SQL" in arrays[0]
    assert "Docker" in arrays[0]
    assert "IT" not in arrays[0]
    assert "ENG" not in arrays[0]
    # Row 2 skills
    assert "React" in arrays[1]
    assert "JavaScript" in arrays[1]
    assert "HTML/CSS" in arrays[1]


@pytest.mark.asyncio
async def test_query_location_demand_compilation_and_execution():
    """Verify that _query_location_demand builds a valid compilable query without NullType CompileError."""
    from sqlalchemy.dialects import postgresql

    agent = MarketAgent()
    mock_db = AsyncMock()

    mock_row1 = MagicMock()
    mock_row1.location = "San Francisco, CA"
    mock_row1.cnt = 10
    mock_row1.avg_sal = 150000.0
    mock_row1.remote_avg = 0.6

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row1]

    async def _fake_execute(stmt):
        # This will raise CompileError if any untyped / NullType expressions exist
        compiled_sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "CASE WHEN" in compiled_sql or "case" in compiled_sql.lower()
        return mock_result

    mock_db.execute = AsyncMock(side_effect=_fake_execute)

    items, total = await agent._query_location_demand(mock_db, title_query="Engineer", top_n=5)

    assert total == 10
    assert len(items) == 1
    assert items[0].location == "San Francisco, CA"
    assert items[0].posting_count == 10
    assert items[0].remote_pct == 60.0
    assert items[0].avg_annual_salary == 150000.0



