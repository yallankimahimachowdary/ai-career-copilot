import pytest
from app.services.parser_agent import parser_agent


SAMPLE_RESUME = """
Alice Sharma
alice.sharma@example.com | (555) 234-5678 | San Francisco, CA
https://linkedin.com/in/alicesharma | https://github.com/alicesharma

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
    assert parsed.contact_info.name == "Alice Sharma"
    assert parsed.contact_info.email == "alice.sharma@example.com"
    assert parsed.contact_info.phone == "(555) 234-5678"
    assert "linkedin.com/in/alicesharma" in (parsed.contact_info.linkedin_url or "")
    assert "github.com/alicesharma" in (parsed.contact_info.github_url or "")


@pytest.mark.asyncio
async def test_parser_agent_skills():
    parsed = await parser_agent.parse(SAMPLE_RESUME)
    assert "Python" in parsed.skills
    assert "FastAPI" in parsed.skills
    assert "Docker" in parsed.skills
    assert "SQL" in parsed.skills
    assert "Redis" in parsed.skills


@pytest.mark.asyncio
async def test_parser_agent_experience_and_education():
    parsed = await parser_agent.parse(SAMPLE_RESUME)
    assert len(parsed.experience) >= 1
    assert any("TechCorp" in exp.company or "TechCorp" in exp.title for exp in parsed.experience)
    assert len(parsed.education) >= 1
    assert any("Berkeley" in edu.institution for edu in parsed.education)


def test_parser_initial_name_and_location():
    resume_text = """S.Kavitha
skavitha.test @example.com
5550192834
Chennai,Tamil Nadu
linkedin.com/in/s-kavitha-test-profile

SUMMARY
Enthusiastic Biotechnology student with knowledge in molecular biology.

EDUCATION
B.Tech-Biotechnology
Vel Tech Institute
"""
    parsed = parser_agent._parse_with_rules(resume_text)
    assert parsed.contact_info.name == "S. Kavitha"
    assert parsed.contact_info.email == "skavitha.test@example.com"
    assert parsed.contact_info.phone == "5550192834"
    assert parsed.contact_info.location == "Chennai, Tamil Nadu"
    assert parsed.contact_info.linkedin_url == "https://linkedin.com/in/s-kavitha-test-profile"


def test_parser_noisy_resume_and_duplicate_skills():
    """Noisy formatting, OCR artifacts, repeated and casing-differed skills must be deduplicated and normalized."""
    noisy_text = """
    ★★★ RESUME - JOHNATHAN DOE ★★★
    Email:  john.doe.dev @ gmail.com | Phone: (123) 456-7890
    Austin, Texas
    
    ### PROFESSIONAL SUMMARY ###
    Dedicated Software Engineer with 5+ years of building resilient services.
    
    === SKILLS & COMPETENCIES ===
    • Python, python, PYTHON, pythOn
    • FastAPI, fastapi, FASTAPI
    • Docker, docker, DOCKER
    • PostgreSQL, sql, Postgres, SQL
    • 2021 - 2024
    • Bachelor of Science in Computer Science
    • University of Texas at Austin
    • High Performer, Hard Working, Team Player
    
    === WORK EXPERIENCE ===
    Backend Lead at CloudCorp Systems
    - Designed and implemented microservices using Python and FastAPI.
    - Containerized pipelines with Docker and managed PostgreSQL databases.
    
    === EDUCATION ===
    University of Texas at Austin
    Bachelor of Science in Computer Science, 2020
    """
    parsed = parser_agent._parse_with_rules(noisy_text)

    # 1. Candidate contact info
    assert parsed.contact_info.email == "john.doe.dev@gmail.com"
    assert parsed.contact_info.phone == "(123) 456-7890"

    # 2. Duplicate skills deduplication and canonicalization
    assert "Python" in parsed.skills
    assert "FastAPI" in parsed.skills
    assert "Docker" in parsed.skills
    assert "SQL" in parsed.skills
    # Check strict uniqueness
    assert len(parsed.skills) == len(set(parsed.skills))
    assert parsed.skills.count("Python") == 1
    assert parsed.skills.count("FastAPI") == 1

    # 3. Non-skill terms excluded from skills
    for invalid in ["2021 - 2024", "Bachelor of Science", "University of Texas", "Hard Working", "Team Player"]:
        assert invalid not in parsed.skills

    # 4. Education and experience preserved
    assert len(parsed.education) >= 1
    assert any("University of Texas" in edu.institution for edu in parsed.education)
    assert len(parsed.experience) >= 1
    assert any("CloudCorp" in exp.company for exp in parsed.experience)


def test_parser_optional_spacy_unavailable(monkeypatch):
    """When spaCy is not installed or model is unavailable, parser runs seamlessly without error."""
    import app.services.parser_agent as pa_module

    # Force spacy to be unavailable
    monkeypatch.setattr(pa_module, "get_spacy_ner", lambda: None)

    resume_text = """
    Alex Rivera
    alex.rivera@example.com | 555-019-2834
    Seattle, Washington
    
    SKILLS
    Python, Linux, Git/GitHub
    
    EDUCATION
    University of Washington
    B.S. in Informatics, 2022
    """
    parsed = pa_module.parser_agent._parse_with_rules(resume_text)
    assert parsed.contact_info.name == "Alex Rivera"
    assert "Python" in parsed.skills
    assert len(parsed.education) >= 1


def test_parser_optional_spacy_fallback_integration(monkeypatch):
    """When heuristic extraction doesn't find name/location in header, spaCy PERSON/GPE entities are used."""
    import app.services.parser_agent as pa_module

    class DummyEntity:
        def __init__(self, text, label):
            self.text = text
            self.label_ = label

    class DummyDoc:
        def __init__(self, text):
            self.ents = [
                DummyEntity("Priya Sharma", "PERSON"),
                DummyEntity("Hyderabad", "GPE"),
                DummyEntity("Tech Innovations", "ORG"),
            ]

    class DummyNlp:
        def __call__(self, text):
            return DummyDoc(text)

    monkeypatch.setattr(pa_module, "get_spacy_ner", lambda: DummyNlp())

    # Raw text where name is not in standard first 10 lines format
    resume_text = """
    Contact via email: priya.s@example.com
    Profile: I am a researcher who worked at Tech Innovations in Hyderabad.
    My colleagues know Priya Sharma as an analytical problem solver.
    
    TECHNICAL SKILLS
    Python, SQL, Machine Learning
    """
    ents = pa_module.parser_agent._extract_spacy_entities(resume_text)
    assert "Priya Sharma" in ents["PERSON"]
    assert "Hyderabad" in ents["GPE"]
    assert "Tech Innovations" in ents["ORG"]


