"""
scripts/build_role_graph_seed.py
--------------------------------
Generates data/graph/role_graph_seed.json with 48 original curated roles
across 5 families with canonical taxonomy skills and valid progression edges.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

ROLES_DATA = [
    # ==========================================
    # 1. WEB & SOFTWARE ENGINEERING (10 roles)
    # ==========================================
    {
        "name": "Junior Web Developer Trainee",
        "family": "web_software",
        "level": "fresher",
        "requires_skills": [
            {"name": "HTML/CSS", "importance": "core"},
            {"name": "JavaScript", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Web Technologies", "importance": "core"},
            {"name": "Communication", "importance": "nice"},
            {"name": "Problem Solving", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Junior Frontend Developer", "typical_years_min": 1, "typical_years_max": 2},
            {"target": "Junior Backend Developer", "typical_years_min": 1, "typical_years_max": 2},
        ],
    },
    {
        "name": "Junior Frontend Developer",
        "family": "web_software",
        "level": "junior",
        "requires_skills": [
            {"name": "HTML/CSS", "importance": "core"},
            {"name": "JavaScript", "importance": "core"},
            {"name": "React", "importance": "core"},
            {"name": "TypeScript", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Web Technologies", "importance": "core"},
            {"name": "Team Collaboration", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Frontend Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Junior Backend Developer",
        "family": "web_software",
        "level": "junior",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "FastAPI", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "REST API", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Software Engineering", "importance": "nice"},
            {"name": "Problem Solving", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Backend Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Frontend Engineer",
        "family": "web_software",
        "level": "mid",
        "requires_skills": [
            {"name": "React", "importance": "core"},
            {"name": "TypeScript", "importance": "core"},
            {"name": "JavaScript", "importance": "core"},
            {"name": "HTML/CSS", "importance": "core"},
            {"name": "REST API", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Agile/Scrum", "importance": "nice"},
            {"name": "Problem Solving", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior Frontend Engineer", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Full Stack Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Backend Engineer",
        "family": "web_software",
        "level": "mid",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "FastAPI", "importance": "core"},
            {"name": "Django", "importance": "nice"},
            {"name": "SQL", "importance": "core"},
            {"name": "MySQL", "importance": "nice"},
            {"name": "REST API", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Software Engineering", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Backend Engineer", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Full Stack Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Full Stack Engineer",
        "family": "web_software",
        "level": "mid",
        "requires_skills": [
            {"name": "React", "importance": "core"},
            {"name": "Node.js", "importance": "core"},
            {"name": "Python", "importance": "nice"},
            {"name": "TypeScript", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "REST API", "importance": "core"},
            {"name": "Docker", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Agile/Scrum", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior Full Stack Engineer", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Staff Software Engineer", "typical_years_min": 4, "typical_years_max": 6},
        ],
    },
    {
        "name": "Senior Frontend Engineer",
        "family": "web_software",
        "level": "senior",
        "requires_skills": [
            {"name": "React", "importance": "core"},
            {"name": "TypeScript", "importance": "core"},
            {"name": "Web Technologies", "importance": "core"},
            {"name": "REST API", "importance": "core"},
            {"name": "GraphQL", "importance": "nice"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Backend Engineer",
        "family": "web_software",
        "level": "senior",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "Java", "importance": "nice"},
            {"name": "FastAPI", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "DBMS", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Redis", "importance": "nice"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Full Stack Engineer",
        "family": "web_software",
        "level": "senior",
        "requires_skills": [
            {"name": "React", "importance": "core"},
            {"name": "TypeScript", "importance": "core"},
            {"name": "Node.js", "importance": "core"},
            {"name": "Python", "importance": "nice"},
            {"name": "SQL", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Agile/Scrum", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Staff Software Engineer",
        "family": "web_software",
        "level": "senior",
        "requires_skills": [
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "Java", "importance": "nice"},
            {"name": "Docker", "importance": "core"},
            {"name": "Kubernetes", "importance": "nice"},
            {"name": "DBMS", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [],
    },

    # ==========================================
    # 2. DATA & ARTIFICIAL INTELLIGENCE (10 roles)
    # ==========================================
    {
        "name": "Associate Data Analyst",
        "family": "data_ai",
        "level": "fresher",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "DBMS", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Communication", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Junior Data Analyst", "typical_years_min": 1, "typical_years_max": 2},
            {"target": "Junior Machine Learning Engineer", "typical_years_min": 1, "typical_years_max": 2},
        ],
    },
    {
        "name": "Junior Data Analyst",
        "family": "data_ai",
        "level": "junior",
        "requires_skills": [
            {"name": "SQL", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "MySQL", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "nice"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Data Analyst", "typical_years_min": 2, "typical_years_max": 3},
            {"target": "Data Scientist", "typical_years_min": 2, "typical_years_max": 4},
        ],
    },
    {
        "name": "Junior Machine Learning Engineer",
        "family": "data_ai",
        "level": "junior",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "Machine Learning", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Docker", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Machine Learning Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Data Analyst",
        "family": "data_ai",
        "level": "mid",
        "requires_skills": [
            {"name": "SQL", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "R Programming", "importance": "nice"},
            {"name": "DBMS", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Data Analyst", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Data Scientist", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Data Scientist",
        "family": "data_ai",
        "level": "mid",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "Machine Learning", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "R Programming", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Data Scientist", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Machine Learning Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Machine Learning Engineer",
        "family": "data_ai",
        "level": "mid",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "Machine Learning", "importance": "core"},
            {"name": "FastAPI", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Machine Learning Engineer", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "AI Research Engineer", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Senior Data Analyst",
        "family": "data_ai",
        "level": "senior",
        "requires_skills": [
            {"name": "SQL", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "DBMS", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Agile/Scrum", "importance": "nice"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Data Scientist",
        "family": "data_ai",
        "level": "senior",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "Machine Learning", "importance": "core"},
            {"name": "SQL", "importance": "core"},
            {"name": "Docker", "importance": "nice"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Machine Learning Engineer",
        "family": "data_ai",
        "level": "senior",
        "requires_skills": [
            {"name": "Python", "importance": "core"},
            {"name": "Machine Learning", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Kubernetes", "importance": "nice"},
            {"name": "FastAPI", "importance": "core"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "AI Research Engineer",
        "family": "data_ai",
        "level": "senior",
        "requires_skills": [
            {"name": "Machine Learning", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "Data Science", "importance": "core"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
        ],
        "leads_to": [],
    },

    # ==========================================
    # 3. CLOUD & DEVOPS ENGINEERING (10 roles)
    # ==========================================
    {
        "name": "Cloud Support Associate",
        "family": "cloud_devops",
        "level": "fresher",
        "requires_skills": [
            {"name": "Linux", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Python", "importance": "nice"},
            {"name": "Communication", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Junior DevOps Engineer", "typical_years_min": 1, "typical_years_max": 2},
            {"target": "Junior Cloud Engineer", "typical_years_min": 1, "typical_years_max": 2},
        ],
    },
    {
        "name": "Junior DevOps Engineer",
        "family": "cloud_devops",
        "level": "junior",
        "requires_skills": [
            {"name": "Linux", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "CI/CD", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Python", "importance": "nice"},
            {"name": "Team Collaboration", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "DevOps Engineer", "typical_years_min": 2, "typical_years_max": 3},
            {"target": "Site Reliability Engineer", "typical_years_min": 2, "typical_years_max": 4},
        ],
    },
    {
        "name": "Junior Cloud Engineer",
        "family": "cloud_devops",
        "level": "junior",
        "requires_skills": [
            {"name": "AWS", "importance": "core"},
            {"name": "Linux", "importance": "core"},
            {"name": "Docker", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Communication", "importance": "nice"},
            {"name": "Problem Solving", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Cloud Infrastructure Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "DevOps Engineer",
        "family": "cloud_devops",
        "level": "mid",
        "requires_skills": [
            {"name": "Docker", "importance": "core"},
            {"name": "Kubernetes", "importance": "core"},
            {"name": "CI/CD", "importance": "core"},
            {"name": "Linux", "importance": "core"},
            {"name": "AWS", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Python", "importance": "nice"},
            {"name": "Agile/Scrum", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior DevOps Engineer", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Platform Engineer", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Cloud Infrastructure Engineer",
        "family": "cloud_devops",
        "level": "mid",
        "requires_skills": [
            {"name": "AWS", "importance": "core"},
            {"name": "Azure", "importance": "nice"},
            {"name": "Linux", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "CI/CD", "importance": "core"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Problem Solving", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior Cloud Architect", "typical_years_min": 4, "typical_years_max": 6},
            {"target": "DevOps Engineer", "typical_years_min": 1, "typical_years_max": 3},
        ],
    },
    {
        "name": "Site Reliability Engineer",
        "family": "cloud_devops",
        "level": "mid",
        "requires_skills": [
            {"name": "Linux", "importance": "core"},
            {"name": "Kubernetes", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "Go", "importance": "nice"},
            {"name": "CI/CD", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Site Reliability Engineer", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Senior DevOps Engineer",
        "family": "cloud_devops",
        "level": "senior",
        "requires_skills": [
            {"name": "Kubernetes", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "AWS", "importance": "core"},
            {"name": "CI/CD", "importance": "core"},
            {"name": "Linux", "importance": "core"},
            {"name": "Kafka", "importance": "nice"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Site Reliability Engineer",
        "family": "cloud_devops",
        "level": "senior",
        "requires_skills": [
            {"name": "Linux", "importance": "core"},
            {"name": "Kubernetes", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Python", "importance": "core"},
            {"name": "AWS", "importance": "nice"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Cloud Architect",
        "family": "cloud_devops",
        "level": "senior",
        "requires_skills": [
            {"name": "AWS", "importance": "core"},
            {"name": "Azure", "importance": "core"},
            {"name": "GCP", "importance": "nice"},
            {"name": "Kubernetes", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Platform Engineer",
        "family": "cloud_devops",
        "level": "senior",
        "requires_skills": [
            {"name": "Kubernetes", "importance": "core"},
            {"name": "Docker", "importance": "core"},
            {"name": "Go", "importance": "nice"},
            {"name": "Python", "importance": "core"},
            {"name": "CI/CD", "importance": "core"},
            {"name": "Linux", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
        ],
        "leads_to": [],
    },

    # ==========================================
    # 4. CORE ENGINEERING (10 roles)
    # ==========================================
    {
        "name": "Graduate Engineering Trainee",
        "family": "core_engineering",
        "level": "fresher",
        "requires_skills": [
            {"name": "AutoCAD", "importance": "core"},
            {"name": "MATLAB", "importance": "nice"},
            {"name": "C", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Junior Mechanical Engineer", "typical_years_min": 1, "typical_years_max": 2},
            {"target": "Junior Embedded Systems Engineer", "typical_years_min": 1, "typical_years_max": 2},
            {"target": "Junior CAD Designer", "typical_years_min": 1, "typical_years_max": 2},
        ],
    },
    {
        "name": "Junior Mechanical Engineer",
        "family": "core_engineering",
        "level": "junior",
        "requires_skills": [
            {"name": "AutoCAD", "importance": "core"},
            {"name": "SolidWorks", "importance": "core"},
            {"name": "ANSYS / FEA", "importance": "nice"},
            {"name": "MATLAB", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Team Collaboration", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Mechanical Design Engineer", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Junior Embedded Systems Engineer",
        "family": "core_engineering",
        "level": "junior",
        "requires_skills": [
            {"name": "C", "importance": "core"},
            {"name": "C/C++", "importance": "core"},
            {"name": "Embedded Systems", "importance": "core"},
            {"name": "MATLAB", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Embedded Systems Engineer", "typical_years_min": 2, "typical_years_max": 3},
            {"target": "Firmware Engineer", "typical_years_min": 2, "typical_years_max": 4},
        ],
    },
    {
        "name": "Junior CAD Designer",
        "family": "core_engineering",
        "level": "junior",
        "requires_skills": [
            {"name": "AutoCAD", "importance": "core"},
            {"name": "Revit / BIM", "importance": "core"},
            {"name": "SolidWorks", "importance": "nice"},
            {"name": "Problem Solving", "importance": "nice"},
            {"name": "Communication", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "CAD/BIM Specialist", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Mechanical Design Engineer",
        "family": "core_engineering",
        "level": "mid",
        "requires_skills": [
            {"name": "SolidWorks", "importance": "core"},
            {"name": "CATIA", "importance": "nice"},
            {"name": "ANSYS / FEA", "importance": "core"},
            {"name": "AutoCAD", "importance": "core"},
            {"name": "CNC Machining", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Mechanical Engineer", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Lead Simulation Engineer", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Embedded Systems Engineer",
        "family": "core_engineering",
        "level": "mid",
        "requires_skills": [
            {"name": "Embedded Systems", "importance": "core"},
            {"name": "C", "importance": "core"},
            {"name": "C/C++", "importance": "core"},
            {"name": "VLSI", "importance": "nice"},
            {"name": "PLC / SCADA", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Embedded Engineer", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Firmware Engineer",
        "family": "core_engineering",
        "level": "mid",
        "requires_skills": [
            {"name": "C", "importance": "core"},
            {"name": "C/C++", "importance": "core"},
            {"name": "Embedded Systems", "importance": "core"},
            {"name": "Linux", "importance": "nice"},
            {"name": "Git/GitHub", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Senior Embedded Engineer", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "CAD/BIM Specialist",
        "family": "core_engineering",
        "level": "mid",
        "requires_skills": [
            {"name": "Revit / BIM", "importance": "core"},
            {"name": "AutoCAD", "importance": "core"},
            {"name": "SolidWorks", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Team Collaboration", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior BIM Coordinator", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Senior Mechanical Engineer",
        "family": "core_engineering",
        "level": "senior",
        "requires_skills": [
            {"name": "SolidWorks", "importance": "core"},
            {"name": "ANSYS / FEA", "importance": "core"},
            {"name": "CATIA", "importance": "nice"},
            {"name": "AutoCAD", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Communication", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Embedded Engineer",
        "family": "core_engineering",
        "level": "senior",
        "requires_skills": [
            {"name": "Embedded Systems", "importance": "core"},
            {"name": "C/C++", "importance": "core"},
            {"name": "VLSI", "importance": "nice"},
            {"name": "Linux", "importance": "nice"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Lead Simulation Engineer",
        "family": "core_engineering",
        "level": "senior",
        "requires_skills": [
            {"name": "ANSYS / FEA", "importance": "core"},
            {"name": "MATLAB", "importance": "core"},
            {"name": "Simulink", "importance": "core"},
            {"name": "SolidWorks", "importance": "nice"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior BIM Coordinator",
        "family": "core_engineering",
        "level": "senior",
        "requires_skills": [
            {"name": "Revit / BIM", "importance": "core"},
            {"name": "AutoCAD", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Time Management", "importance": "nice"},
        ],
        "leads_to": [],
    },

    # ==========================================
    # 5. BUSINESS & PRODUCT (8 roles)
    # ==========================================
    {
        "name": "Associate Product Analyst",
        "family": "business_nontech",
        "level": "fresher",
        "requires_skills": [
            {"name": "Communication", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "SQL", "importance": "nice"},
            {"name": "Agile/Scrum", "importance": "nice"},
            {"name": "Team Collaboration", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Junior Product Manager", "typical_years_min": 1, "typical_years_max": 2},
            {"target": "Junior Business Analyst", "typical_years_min": 1, "typical_years_max": 2},
        ],
    },
    {
        "name": "Junior Product Manager",
        "family": "business_nontech",
        "level": "junior",
        "requires_skills": [
            {"name": "Agile/Scrum", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "SQL", "importance": "nice"},
            {"name": "Figma", "importance": "nice"},
            {"name": "Time Management", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Product Manager", "typical_years_min": 2, "typical_years_max": 3},
            {"target": "Scrum Master", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Junior Business Analyst",
        "family": "business_nontech",
        "level": "junior",
        "requires_skills": [
            {"name": "SQL", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Data Science", "importance": "nice"},
            {"name": "Team Collaboration", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Business Analyst", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Product Manager",
        "family": "business_nontech",
        "level": "mid",
        "requires_skills": [
            {"name": "Agile/Scrum", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "SQL", "importance": "nice"},
            {"name": "Software Engineering", "importance": "nice"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Figma", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior Product Manager", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Technical Program Manager", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Business Analyst",
        "family": "business_nontech",
        "level": "mid",
        "requires_skills": [
            {"name": "SQL", "importance": "core"},
            {"name": "Data Science", "importance": "nice"},
            {"name": "Communication", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Agile/Scrum", "importance": "nice"},
            {"name": "Time Management", "importance": "nice"},
        ],
        "leads_to": [
            {"target": "Senior Business Analyst", "typical_years_min": 3, "typical_years_max": 5},
            {"target": "Product Manager", "typical_years_min": 2, "typical_years_max": 3},
        ],
    },
    {
        "name": "Scrum Master",
        "family": "business_nontech",
        "level": "mid",
        "requires_skills": [
            {"name": "Agile/Scrum", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Team Collaboration", "importance": "core"},
            {"name": "Time Management", "importance": "core"},
        ],
        "leads_to": [
            {"target": "Agile Project Manager", "typical_years_min": 3, "typical_years_max": 5},
        ],
    },
    {
        "name": "Senior Product Manager",
        "family": "business_nontech",
        "level": "senior",
        "requires_skills": [
            {"name": "Agile/Scrum", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
            {"name": "Software Engineering", "importance": "nice"},
            {"name": "Time Management", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Senior Business Analyst",
        "family": "business_nontech",
        "level": "senior",
        "requires_skills": [
            {"name": "SQL", "importance": "core"},
            {"name": "DBMS", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Problem Solving", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Technical Program Manager",
        "family": "business_nontech",
        "level": "senior",
        "requires_skills": [
            {"name": "Agile/Scrum", "importance": "core"},
            {"name": "Software Engineering", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Time Management", "importance": "core"},
        ],
        "leads_to": [],
    },
    {
        "name": "Agile Project Manager",
        "family": "business_nontech",
        "level": "senior",
        "requires_skills": [
            {"name": "Agile/Scrum", "importance": "core"},
            {"name": "Leadership", "importance": "core"},
            {"name": "Team Collaboration", "importance": "core"},
            {"name": "Communication", "importance": "core"},
            {"name": "Time Management", "importance": "core"},
        ],
        "leads_to": [],
    },
]


def build_and_save():
    payload = {
        "metadata": {
            "source": "curated_seed",
            "version": "1.0",
            "total_roles": len(ROLES_DATA),
            "note": "Curated seed role ontology. LEADS_TO edges are assumptions, not empirical career data.",
        },
        "roles": ROLES_DATA,
    }

    out_path = os.path.join("data", "graph", "role_graph_seed.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Generated {len(ROLES_DATA)} roles into {out_path}")


if __name__ == "__main__":
    build_and_save()
