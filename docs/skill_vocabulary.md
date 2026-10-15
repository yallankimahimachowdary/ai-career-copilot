# Skill Vocabulary & Taxonomy Documentation

## Overview
This document specifies the canonical skill vocabulary and normalization mappings employed across AI Career Copilot's matching, coaching, market, and ranking subsystems (`app/core/taxonomy.py`, `app/ranking/`, and `app/services/matcher_service.py`).

## Relationship to ESCO and O*NET Standards
- **Standardized Frameworks**: The taxonomy adheres to concepts defined in the European Commission's **ESCO** (European Skills, Competences, Qualifications and Occupations) taxonomy and the U.S. Department of Labor's **O\*NET** (Occupational Information Network) 28.0 knowledge/skill descriptors.
- **Hierarchical Clustering**: Technical skills are clustered into primary competency domains (Languages, Frameworks, Cloud/Infrastructure, AI/ML/Data, Design/3D, Domain-Specific Disciplines).
- **Soft Skills Separation**: Soft skills (e.g. Communication, Problem Solving, Leadership, Teamwork) are partitioned into a distinct non-technical subset (`SOFT_SKILLS`). They are treated as growth/coaching targets rather than hard gating constraints to prevent false negatives in automated re-ranking.
- **Categorical Noise Elimination**: LinkedIn-specific job function abbreviations (such as `ENG`, `QA`, `IT`, `MGMT`, `FIN`) from raw job postings datasets are explicitly filtered via `LINKEDIN_CATEGORY_CODES` to eliminate false substring collisions and TreeSHAP attribution distortions.

---

## Canonical Skills and Synonym Mappings

| Canonical Skill | Cluster / Category | Standard Mapping / Synonyms | Regex Boundary Pattern |
| :--- | :--- | :--- | :--- |
| **Python** | Languages | Python, Py, Python3 | `\bpython\b` |
| **Java** | Languages | Java, Core Java (excludes JavaScript) | `\bjava\b(?!\s*script)` |
| **JavaScript** | Languages | JS, ECMAScript, JavaScript | `\b(javascript\|js\|ecmascript)\b` |
| **TypeScript** | Languages | TypeScript, TS | `\b(typescript\|ts)\b` |
| **C/C++** | Languages | C, C++, C Programming, Embedded C | `\b(c\+\+\|c\s*programming\|embedded\s*c)\b` |
| **C#** | Languages | C#, C Sharp, .NET, DotNet | `\b(c#\|c\s*sharp\|\.net)\b` |
| **SQL** | Databases | SQL, MySQL, PostgreSQL, Postgres, SQLite, PL/SQL | `\b(sql\|mysql\|postgresql\|postgres\|sqlite\|pl\/sql)\b` |
| **HTML/CSS** | Web Frontend | HTML, HTML5, CSS, CSS3, Web Technologies | `\b(html5?\|css3?)\b` |
| **React** | Web Frameworks | React, React.js, ReactJS, React Native | `\breact(?:\.js\|js\|\s*native)?\b` |
| **FastAPI** | Backend Frameworks | FastAPI, Fast API | `\b(fastapi\|fast\s*api)\b` |
| **Django** | Backend Frameworks | Django, Django REST Framework | `\bdjango\b` |
| **Flask** | Backend Frameworks | Flask | `\bflask\b` |
| **Spring Boot** | Backend Frameworks | Spring Boot, Spring Framework | `\b(spring\s*boot\|spring\s*framework)\b` |
| **Node.js** | Backend Runtimes | Node.js, Node, NodeJS | `\b(node(?:\.js\|js)?)\b` |
| **Docker** | DevOps & Cloud | Docker, Containerization | `\bdocker\b` |
| **Kubernetes** | DevOps & Cloud | Kubernetes, K8s | `\b(kubernetes\|k8s)\b` |
| **AWS** | DevOps & Cloud | Amazon Web Services, AWS | `\b(aws\|amazon\s*web\s*services)\b` |
| **Azure** | DevOps & Cloud | Microsoft Azure, Azure Cloud | `\bazure\b` |
| **GCP** | DevOps & Cloud | Google Cloud Platform, GCP | `\b(gcp\|google\s*cloud)\b` |
| **Git/GitHub** | Version Control | Git, GitHub, GitLab | `\b(git\|github\|gitlab)\b` |
| **Linux** | Operating Systems | Linux, Unix, Ubuntu, CentOS | `\b(linux\|unix\|ubuntu\|centos)\b` |
| **REST API** | API Architecture | REST API, RESTful, GraphQL, Microservices | `\b(rest(?:\s*api\|\s*framework)?\|restful\|graphql\|microservices)\b` |
| **Machine Learning**| AI & Data Science | Machine Learning, ML, Deep Learning, PyTorch, TensorFlow, Scikit-Learn | `\b(machine\s*learning\|deep\s*learning\|pytorch\|tensorflow\|keras\|scikit.learn\|nlp\|computer\s*vision)\b` |
| **Data Science** | AI & Data Science | Data Science, Data Analytics, Pandas, NumPy, Spark | `\b(data\s*science\|data\s*analytics?\|pandas\|numpy\|spark)\b` |
| **Blender/3D** | Creative Design | Blender, 3D Modeling, Blender & Creative Design | `\b(blender\|3d\s*modeling)\b` |
| **Communication** | Soft Skills | Communication, Collaboration, Teamwork, Interpersonal | `\b(communication\|collaboration\|teamwork\|interpersonal)\b` |
| **Problem Solving**| Soft Skills | Problem Solving, Critical Thinking, Analytical | `\b(problem.solving\|analytical\|critical\s*thinking)\b` |
| **Leadership** | Soft Skills | Leadership, Mentoring, Team Lead | `\b(leadership\|mentoring\|team\s*lead)\b` |

---

## Evaluation Benchmark & Quality Standards
The parser evaluation tool (`scripts/eval_parser.py`) compares model and regex extraction against ground truth hand-annotated resumes in `data/gold/gold_resumes_skills.json`.

- **Precision Target**: >= 0.70 on production domain vocabulary.
- **Recall Target**: >= 0.85 across core canonical skills.
- **F1 Harmonization**: Regularization against synonym drift to guarantee reproducible ranking and explanations.
