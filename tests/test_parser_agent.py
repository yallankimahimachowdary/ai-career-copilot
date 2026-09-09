import pytest
from app.services.parser_agent import parser_agent


SAMPLE_RESUME = """
Mahima Sharma
mahima.sharma@example.com | (555) 234-5678 | San Francisco, CA
https://linkedin.com/in/mahimasharma | https://github.com/mahimasharma

PROFESSIONAL SUMMARY
Experienced Full-Stack and AI Engineer with expertise in building scalable backend systems,
generative AI applications, and cloud microservices.

TECHNICAL SKILLS
Python, FastAPI, Docker, PostgreSQL, Redis, SQLAlchemy, Git, Linux, PyTorch, React

WORK EXPERIENCE
Senior Backend Engineer at TechCorp Inc.
- Architected high-throughput REST APIs using FastAPI and asyncpg, handling 10M requests daily.
- Integrated pgvector and vector embeddings for semantic job recommendation pipelines.
- Reduced database query latency by 45% through Redis caching and query indexing.

Software Engineer at CloudScale Solutions
- Developed microservices with Python and Docker on AWS.
- Built automated CI/CD pipelines and unit tests using Pytest.

EDUCATION
University of California, Berkeley
B.S. in Computer Science, 2021

PROJECTS
AI Career Copilot
- Intelligent multi-agent system for resume optimization and career guidance.
"""


@pytest.mark.asyncio
async def test_parser_agent_contact_info():
    parsed = await parser_agent.parse(SAMPLE_RESUME)
    assert parsed.contact_info.name == "Mahima Sharma"
    assert parsed.contact_info.email == "mahima.sharma@example.com"
    assert parsed.contact_info.phone == "(555) 234-5678"
    assert "linkedin.com/in/mahimasharma" in (parsed.contact_info.linkedin_url or "")
    assert "github.com/mahimasharma" in (parsed.contact_info.github_url or "")


@pytest.mark.asyncio
async def test_parser_agent_skills():
    parsed = await parser_agent.parse(SAMPLE_RESUME)
    assert "Python" in parsed.skills
    assert "FastAPI" in parsed.skills
    assert "Docker" in parsed.skills
    assert "PostgreSQL" in parsed.skills
    assert "Redis" in parsed.skills


@pytest.mark.asyncio
async def test_parser_agent_experience_and_education():
    parsed = await parser_agent.parse(SAMPLE_RESUME)
    assert len(parsed.experience) >= 1
    assert any("TechCorp" in exp.company or "TechCorp" in exp.title for exp in parsed.experience)
    assert len(parsed.education) >= 1
    assert any("Berkeley" in edu.institution for edu in parsed.education)
