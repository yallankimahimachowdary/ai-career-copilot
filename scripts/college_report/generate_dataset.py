"""
scripts/college_report/generate_dataset.py
-----------------------------------------
Deterministic, seeded generator for College Project Demo & Evaluation.
Creates:
1. 20 Synthetic Resumes (structured text and ground-truth expected values)
2. 10 Synthetic Job Postings (titles, families, required skills)
3. Ground-truth expected parsing values (name, skills, education, experience)
4. Ground-truth relevance labels for all 200 resume-job pairs based on an explicit written rule.
5. Table 1: Synthetic Dataset Description (CSV + Markdown)

LABEL: SYNTHETIC DATASET -- For Academic Project Demonstration Only.
Relevance is defined by the generator's explicit rule and the matcher also uses skills,
so the scores show consistent behaviour on synthetic data, not accuracy on real candidates.
"""

from collections import Counter
import csv
import json
from pathlib import Path
import random
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SEED = 42
random.seed(SEED)

DEMO_DIR = PROJECT_ROOT / "data" / "college_demo"
RESUMES_DIR = DEMO_DIR / "resumes"
OUTPUT_DIR = PROJECT_ROOT / "results" / "college_report"

DEMO_DIR.mkdir(parents=True, exist_ok=True)
RESUMES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Domain Taxonomies & Skill Sets
# -----------------------------------------------------------------------------

ROLE_FAMILIES = {
    "Data/AI": {
        "titles": ["Data Scientist", "Machine Learning Engineer", "Data Analyst", "AI Engineer"],
        "skills": ["Python", "Machine Learning", "SQL", "Pandas", "Scikit-Learn", "PyTorch", "TensorFlow", "Deep Learning", "Data Visualization", "NLP"],
    },
    "Web/Software": {
        "titles": ["Backend Engineer", "Frontend Developer", "Full Stack Engineer", "DevOps Engineer"],
        "skills": ["Python", "FastAPI", "React", "JavaScript", "TypeScript", "Node.js", "Docker", "PostgreSQL", "Git", "REST APIs"],
    },
    "Cybersecurity/Cloud": {
        "titles": ["Cloud Architect", "Security Analyst", "Cloud Security Engineer", "DevSecOps Engineer"],
        "skills": ["AWS", "Docker", "Kubernetes", "Linux", "Network Security", "Cryptography", "IAM", "Terraform", "CI/CD", "Firewalls"],
    },
    "Mobile/UI-UX": {
        "titles": ["Android Developer", "iOS Developer", "UI/UX Designer", "Mobile App Engineer"],
        "skills": ["Kotlin", "Swift", "Flutter", "Figma", "UI/UX Design", "Wireframing", "REST APIs", "Mobile Design", "React Native", "Git"],
    },
}

NAMES = [
    ("Aarav", "Sharma"), ("Aditi", "Patel"), ("Vikram", "Reddy"), ("Ananya", "Deshmukh"),
    ("Rohan", "Mehta"), ("Pooja", "Nair"), ("Siddharth", "Verma"), ("Neha", "Kulkarni"),
    ("Kavya", "Iyer"), ("Arjun", "Menon"), ("Priya", "Chopra"), ("Rahul", "Sen"),
    ("Tanvi", "Naidu"), ("Kunal", "Bose"), ("Divya", "Hegde"), ("Akash", "Rao"),
    ("Sneha", "Joshi"), ("Varun", "Bhat"), ("Meera", "Pillai"), ("Tarun", "Gupta"),
]

UNIVERSITIES = [
    "Indian Institute of Technology Madras", "National Institute of Technology Karnataka",
    "Birla Institute of Technology and Science Pilani", "Vellore Institute of Technology",
    "Delhi Technological University", "Anna University Chennai",
]

COMPANIES = [
    "TechCorp Solutions", "DataPulse Analytics", "CloudNative Systems",
    "InnoSoft Innovations", "NextGen Digital", "CyberShield Labs",
]


def generate_candidates():
    candidates = []
    fams = list(ROLE_FAMILIES.keys())
    levels = ["junior", "mid", "senior"]

    for i in range(20):
        cid = f"SYN_DEMO_{i+1:03d}"
        fname, lname = NAMES[i]
        full_name = f"{fname} {lname}"
        fam = fams[i % len(fams)]
        level = levels[i % len(levels)]
        title = ROLE_FAMILIES[fam]["titles"][i % len(ROLE_FAMILIES[fam]["titles"])]

        # Sample skills
        pool = ROLE_FAMILIES[fam]["skills"]
        n_skills = 6 if level == "junior" else (8 if level == "mid" else 9)
        c_skills = sorted(random.sample(pool, min(n_skills, len(pool))))

        # Degree & Education
        uni = UNIVERSITIES[i % len(UNIVERSITIES)]
        grad_year = 2024 if level == "junior" else (2021 if level == "mid" else 2017)
        degree = "B.Tech in Computer Science" if i % 2 == 0 else "M.Tech in Information Technology"

        # Experience
        years_exp = 1 if level == "junior" else (4 if level == "mid" else 8)
        comp = COMPANIES[i % len(COMPANIES)]

        exp_entries = [
            {
                "company": comp,
                "role": f"{level.capitalize()} {title}",
                "years": years_exp,
            }
        ]
        if level == "senior":
            prev_comp = COMPANIES[(i + 1) % len(COMPANIES)]
            exp_entries.append({
                "company": prev_comp,
                "role": f"Mid {title}",
                "years": 3,
            })

        # Synthetic Resume Text
        resume_text = f"""{full_name}
Email: {fname.lower()}.{lname.lower()}@example.com | Phone: +91-987654{i:04d} | Location: Bangalore, India
LinkedIn: linkedin.com/in/{fname.lower()}{lname.lower()} | GitHub: github.com/{fname.lower()}{lname.lower()}

PROFESSIONAL SUMMARY
Results-driven {title} with {years_exp}+ years of experience in {fam} environments. Proven expertise in {', '.join(c_skills[:3])}. Demonstrated track record of delivering high-impact solutions.

TECHNICAL SKILLS
- Core Skills: {', '.join(c_skills)}
- Methodologies: Agile/Scrum, Version Control, Continuous Integration, Code Review

PROFESSIONAL EXPERIENCE
"""
        for exp in exp_entries:
            resume_text += f"""{exp['role']} | {exp['company']} ({exp['years']} years)
- Architected and implemented scalable features leveraging {c_skills[0]} and {c_skills[1]}.
- Collaborated across functional teams to improve code quality, system latency, and throughput.
- Optimized development pipelines utilizing modern engineering best practices.

"""

        resume_text += f"""EDUCATION
{degree}
{uni}, Graduated: {grad_year}

CERTIFICATIONS
- Certified Professional in {c_skills[0]} Fundamentals
- Professional Software Engineering Standards Certificate
"""

        txt_path = RESUMES_DIR / f"{cid}.txt"
        txt_path.write_text(resume_text, encoding="utf-8")

        candidates.append({
            "candidate_id": cid,
            "candidate_name": full_name,
            "role_family": fam,
            "seniority_level": level,
            "target_role": title,
            "expected_skills": c_skills,
            "expected_education": {
                "degree": degree,
                "institution": uni,
                "graduation_year": grad_year,
            },
            "expected_experience": exp_entries,
            "file_path": str(txt_path).replace("\\", "/"),
        })

    return candidates


def generate_jobs():
    jobs = []
    job_specs = [
        ("JOB_DEMO_001", "Senior Data Scientist", "Data/AI", ["Python", "Machine Learning", "PyTorch", "SQL", "Scikit-Learn", "Deep Learning"]),
        ("JOB_DEMO_002", "Associate Machine Learning Engineer", "Data/AI", ["Python", "Machine Learning", "TensorFlow", "Pandas", "Git"]),
        ("JOB_DEMO_003", "Data Analyst", "Data/AI", ["SQL", "Pandas", "Data Visualization", "Python"]),
        ("JOB_DEMO_004", "Full Stack Developer", "Web/Software", ["React", "Node.js", "TypeScript", "PostgreSQL", "REST APIs", "Git"]),
        ("JOB_DEMO_005", "Backend Python Engineer", "Web/Software", ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"]),
        ("JOB_DEMO_006", "DevOps & Cloud Engineer", "Web/Software", ["Docker", "Git", "PostgreSQL", "CI/CD", "Linux", "REST APIs"]),
        ("JOB_DEMO_007", "Cloud Security Architect", "Cybersecurity/Cloud", ["AWS", "Kubernetes", "IAM", "Network Security", "Terraform", "Linux"]),
        ("JOB_DEMO_008", "Cybersecurity Analyst", "Cybersecurity/Cloud", ["Network Security", "Cryptography", "Linux", "Firewalls", "IAM"]),
        ("JOB_DEMO_009", "Senior Android Engineer", "Mobile/UI-UX", ["Kotlin", "REST APIs", "Git", "Flutter", "Mobile Design"]),
        ("JOB_DEMO_010", "UI/UX Product Designer", "Mobile/UI-UX", ["Figma", "UI/UX Design", "Wireframing", "Mobile Design"]),
    ]

    for jid, title, fam, skills in job_specs:
        jobs.append({
            "job_id": jid,
            "title": title,
            "role_family": fam,
            "required_skills": skills,
            "description": f"Seeking a passionate {title} to build high-performance systems. Required proficiency in {', '.join(skills)}.",
        })

    return jobs


def build_pairwise_ground_truth(candidates, jobs):
    """
    Explicit written relevance rule:
    Relevance Label:
    - 2 (Strong Fit): candidate.role_family == job.role_family AND matched_skills >= 0.70 * required_skills
    - 1 (Partial Fit): candidate.role_family == job.role_family AND matched_skills >= 0.40 * required_skills
    - 0 (Not Relevant): mismatched role family OR matched_skills < 0.40 * required_skills
    """
    pairs = []
    for cand in candidates:
        c_skills_set = set(cand["expected_skills"])
        for job in jobs:
            j_skills_set = set(job["required_skills"])
            matched = sorted(list(c_skills_set.intersection(j_skills_set)))
            missing = sorted(list(j_skills_set.difference(c_skills_set)))
            ratio = len(matched) / len(j_skills_set) if j_skills_set else 0.0

            if cand["role_family"] == job["role_family"]:
                if ratio >= 0.70:
                    label = 2
                    label_desc = "Strong Fit"
                elif ratio >= 0.40:
                    label = 1
                    label_desc = "Partial Fit"
                else:
                    label = 0
                    label_desc = "Not Relevant"
            else:
                label = 0
                label_desc = "Not Relevant (Cross-Domain)"

            pairs.append({
                "candidate_id": cand["candidate_id"],
                "candidate_name": cand["candidate_name"],
                "job_id": job["job_id"],
                "job_title": job["title"],
                "candidate_family": cand["role_family"],
                "job_family": job["role_family"],
                "matched_skills": matched,
                "missing_skills": missing,
                "match_ratio": round(ratio, 4),
                "relevance_label": label,
                "relevance_desc": label_desc,
            })

    return pairs


def write_table_1(candidates, jobs, pairs):
    fam_cands = Counter(c["role_family"] for c in candidates)
    fam_jobs = Counter(j["role_family"] for j in jobs)
    levels = Counter(c["seniority_level"] for c in candidates)
    labels = Counter(p["relevance_label"] for p in pairs)

    avg_cand_skills = sum(len(c["expected_skills"]) for c in candidates) / len(candidates)
    avg_job_skills = sum(len(j["required_skills"]) for j in jobs) / len(jobs)

    rows = [
        ["Total Synthetic Resumes", str(len(candidates)), "4 Role Families (5 per family)"],
        ["Total Synthetic Job Descriptions", str(len(jobs)), "4 Role Families (2-3 per family)"],
        ["Seniority Breakdown (Resumes)", f"Junior: {levels['junior']}, Mid: {levels['mid']}, Senior: {levels['senior']}", "Balanced Career Experience Spectrum"],
        ["Role Family: Data/AI", f"{fam_cands['Data/AI']} Resumes, {fam_jobs['Data/AI']} Jobs", "Data Science, ML, AI Engineering"],
        ["Role Family: Web/Software", f"{fam_cands['Web/Software']} Resumes, {fam_jobs['Web/Software']} Jobs", "Frontend, Backend, DevOps, Full-Stack"],
        ["Role Family: Cybersecurity/Cloud", f"{fam_cands['Cybersecurity/Cloud']} Resumes, {fam_jobs['Cybersecurity/Cloud']} Jobs", "Cloud Architecture, DevSecOps, InfoSec"],
        ["Role Family: Mobile/UI-UX", f"{fam_cands['Mobile/UI-UX']} Resumes, {fam_jobs['Mobile/UI-UX']} Jobs", "Android, iOS, UI/UX Product Design"],
        ["Average Skills per Resume", f"{avg_cand_skills:.1f}", "Extracted from standardized technical skill pools"],
        ["Average Skills per Job Description", f"{avg_job_skills:.1f}", "Explicit core technical requirements"],
        ["Total Evaluated Pairs", str(len(pairs)), "Full Cartesian Product (20 x 10)"],
        ["Relevance: Strong Fit (rel=2)", f"{labels[2]} pairs ({labels[2]/len(pairs)*100:.1f}%)", "Same domain and >=70% required skill overlap"],
        ["Relevance: Partial Fit (rel=1)", f"{labels[1]} pairs ({labels[1]/len(pairs)*100:.1f}%)", "Same domain and 40-69% required skill overlap"],
        ["Relevance: Not Relevant (rel=0)", f"{labels[0]} pairs ({labels[0]/len(pairs)*100:.1f}%)", "Cross-domain family or <40% skill overlap"],
    ]

    csv_path = OUTPUT_DIR / "table_1_dataset_description.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Dataset Metric / Dimension", "Value / Count", "Description & Domain Scope"])
        writer.writerows(rows)

    md_lines = [
        "# Table 1: Synthetic Evaluation Dataset Description",
        "",
        "> **SYNTHETIC BENCHMARK -- Generated programmatically for college project evaluation.**",
        "> *Relevance is defined by the generator's explicit rule and the matcher also uses skills, so the scores show consistent behaviour on synthetic data, not accuracy on real candidates.*",
        "",
        "| Dataset Metric / Dimension | Value / Count | Description & Domain Scope |",
        "| :--- | :---: | :--- |",
    ]
    for r in rows:
        md_lines.append(f"| {r[0]} | {r[1]} | {r[2]} |")

    md_path = OUTPUT_DIR / "table_1_dataset_description.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"[SUCCESS] Table 1 saved to: {csv_path} and {md_path}")


def main():
    print("=================================================================")
    print("   GENERATING SYNTHETIC EVALUATION DATASET & GROUND TRUTH       ")
    print("=================================================================")
    candidates = generate_candidates()
    jobs = generate_jobs()
    pairs = build_pairwise_ground_truth(candidates, jobs)

    # Save Ground Truth Manifest
    gt_data = {
        "metadata": {
            "dataset_label": "SYNTHETIC_COLLEGE_DEMO",
            "seed": SEED,
            "note": "Relevance is defined by the generator's rule and the matcher also uses skills, so the scores show consistent behaviour on synthetic data, not accuracy on real candidates.",
            "total_candidates": len(candidates),
            "total_jobs": len(jobs),
            "total_pairs": len(pairs),
        },
        "candidates": candidates,
        "jobs": jobs,
        "pairwise_ground_truth": pairs,
    }

    gt_file = DEMO_DIR / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_data, f, indent=2)

    # Save Jobs List
    jobs_file = DEMO_DIR / "jobs.json"
    with open(jobs_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)

    print(f"[SUCCESS] Generated {len(candidates)} synthetic resumes in: {RESUMES_DIR}")
    print(f"[SUCCESS] Generated {len(jobs)} synthetic jobs in: {jobs_file}")
    print(f"[SUCCESS] Saved ground truth to: {gt_file}")

    write_table_1(candidates, jobs, pairs)


if __name__ == "__main__":
    main()
