"""Tests for Resume PII Anonymizer Service."""

from app.services.anonymizer import anonymize_resume


def test_anonymize_email_and_phone():
    text = "Contact me at synthetic.candidate77@gmail.com or call +91-9876543210."
    result = anonymize_resume(text)
    assert "[EMAIL]" in result
    assert "synthetic.candidate77@gmail.com" not in result
    assert "[PHONE]" in result
    assert "9876543210" not in result


def test_anonymize_links_and_urls():
    text = "GitHub: https://github.com/candidatetest and LinkedIn: linkedin.com/in/candidatetest"
    result = anonymize_resume(text)
    assert "https://github.com" not in result
    assert "[LINK]" in result


def test_anonymize_candidate_initials():
    text = "Resume of K.Suresh, Biotechnology specialist. K. Suresh researched oncology."
    result = anonymize_resume(text, candidate_name="K.Suresh")
    assert "K.Suresh" not in result
    assert "K. Suresh" not in result
    assert "K." not in result
    assert "Suresh" not in result
    assert "[NAME]" in result


def test_anonymize_spaced_initial_and_suffix():
    text = "Suresh K. worked on bioinformatics pipeline. Contact K Suresh for details."
    result = anonymize_resume(text, candidate_name="K.Suresh")
    assert "Suresh" not in result
    assert "Suresh K." not in result
    assert "K Suresh" not in result
    assert "[NAME]" in result


def test_anonymize_multiword_name():
    text = "Candidate PRIYA ANANYA SHARMA has 3 years of Python experience."
    result = anonymize_resume(text, candidate_name="PRIYA ANANYA SHARMA")
    assert "ANANYA" not in result
    assert "SHARMA" not in result
    assert "PRIYA" not in result
    assert "[NAME]" in result


def test_anonymize_physical_address():
    """Verify physical street, flat, colony, and nagar address masking."""
    text1 = "Residing at Flat 302, Green Glen Layout, Bellandur, Bengaluru."
    res1 = anonymize_resume(text1)
    assert "[ADDRESS]" in res1
    assert "Green Glen Layout" not in res1

    text2 = "Address: 742 Evergreen Terrace, Springfield, OR"
    res2 = anonymize_resume(text2)
    assert "[ADDRESS]" in res2
    assert "742 Evergreen Terrace" not in res2

    text3 = "Plot No. 45, Jubilee Hills Road No. 36, Hyderabad"
    res3 = anonymize_resume(text3)
    assert "[ADDRESS]" in res3
    assert "Jubilee Hills" not in res3


def test_anonymize_pincodes():
    """Verify masking of 6-digit Indian PIN codes and labeled PIN/ZIP codes."""
    text1 = "Location: Bengaluru, Karnataka - 560103."
    res1 = anonymize_resume(text1)
    assert "[PINCODE]" in res1
    assert "560103" not in res1

    text2 = "PIN: 500032 and postal code: 600028"
    res2 = anonymize_resume(text2)
    assert "[PINCODE]" in res2
    assert "500032" not in res2
    assert "600028" not in res2

    text3 = "ZIP: 94107-1234, San Francisco, CA"
    res3 = anonymize_resume(text3)
    assert "[PINCODE]" in res3
    assert "94107" not in res3


def test_anonymize_strip_institutions_default_true():
    """Verify that universities, colleges, and institutes are stripped by default to prevent prestige bias."""
    text = (
        "Graduated from Stanford University with B.S. in Computer Science. "
        "Completed master's thesis at Indian Institute of Technology Madras and did research at MIT."
    )
    result = anonymize_resume(text, strip_institutions=True)
    assert "[INSTITUTION]" in result
    assert "Stanford University" not in result
    assert "Indian Institute of Technology Madras" not in result
    assert "MIT" not in result


def test_anonymize_strip_institutions_false():
    """Verify that institutions are preserved when strip_institutions=False."""
    text = "Graduated from Stanford University and Birla Institute of Technology."
    result = anonymize_resume(text, strip_institutions=False)
    assert "Stanford University" in result
    assert "Birla Institute of Technology" in result
    assert "[INSTITUTION]" not in result


def test_anonymize_full_sample_resume_fake_data():
    """Verify end-to-end anonymization of a comprehensive fake resume."""
    fake_resume = """Alex Morgan
alex.morgan99@example.com | +1 (555) 839-2041 | GitHub: github.com/alexmorgan-dev
Address: Apartment 4B, 120 Oak Street, Austin, TX 78701
LinkedIn: linkedin.com/in/alex-morgan-swe

SUMMARY
Experienced Full Stack Engineer with 4 years building scalable microservices in Python and TypeScript.

EDUCATION
Bachelor of Science in Software Engineering
University of Texas at Austin, Class of 2021
Relevant Coursework: Distributed Systems, Operating Systems, Machine Learning

EXPERIENCE
Software Engineer | Acme Cloud Systems (2021 - Present)
- Engineered real-time data pipelines using FastAPI, PostgreSQL, and Apache Kafka.
- Containerized microservices using Docker and orchestrated deployments on Kubernetes.
- Decreased API latency by 35% through query optimization and Redis caching.

Junior Developer | Tech Innovators LLC (2020 - 2021)
- Developed responsive web interfaces in React and Next.js.
- Integrated RESTful APIs and wrote automated unit tests with Jest.

SKILLS
Languages: Python, JavaScript, TypeScript, SQL
Frameworks: FastAPI, React, Node.js, Next.js
Tools: Docker, Kubernetes, Git, PostgreSQL, Redis
"""
    anonymized = anonymize_resume(fake_resume, candidate_name="Alex Morgan", strip_institutions=True)

    # Candidate Name must be masked
    assert "Alex Morgan" not in anonymized
    assert "alex.morgan" not in anonymized
    # Email must be masked
    assert "alex.morgan99@example.com" not in anonymized
    assert "[EMAIL]" in anonymized
    # Phone must be masked
    assert "839-2041" not in anonymized
    assert "[PHONE]" in anonymized
    # Hyperlinks must be masked
    assert "github.com/alexmorgan-dev" not in anonymized
    assert "linkedin.com/in/alex-morgan-swe" not in anonymized
    assert "[LINK]" in anonymized
    # Address and ZIP code must be masked
    assert "120 Oak Street" not in anonymized
    assert "78701" not in anonymized
    assert "[ADDRESS]" in anonymized or "[PINCODE]" in anonymized
    # University must be masked
    assert "University of Texas" not in anonymized
    assert "[INSTITUTION]" in anonymized

    # Core competencies and substantive text must be preserved
    assert "FastAPI" in anonymized
    assert "PostgreSQL" in anonymized
    assert "Docker" in anonymized
    assert "Kubernetes" in anonymized
    assert "microservices" in anonymized
