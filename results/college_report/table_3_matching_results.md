# Table 3: Resume-Job Matching Results (20 Candidates x 10 Jobs = 200 Pairs)

> **SYNTHETIC BENCHMARK -- Generated programmatically for college project evaluation.**
> *Note: Relevance is defined by the generator's rule (role family alignment and skill overlap threshold) and the matcher also uses skills and dense semantics, so these numbers show consistent and reproducible behavior on synthetic benchmark data, not accuracy on real human candidates.*
> *Methodology & P@2 Cap Note: Scores produced by `HybridRanker` (`app.ranking.hybrid`) with frozen weights (BM25: 0.10, SBERT: 0.10, Skill Overlap: 0.80). Skill overlap carries 80% of the hybrid score; scores are min-max normalised per candidate across the candidate's pool of 10 jobs; 20 of 20 candidates (100.0%) have at least 2 relevant jobs in the ground truth pool, setting the theoretical cap on P@2 at 1.0 (100.0%).* 

### Item 6b: Per-Candidate Top-1 Recommendation View:
> *Note: Normalised scores are min-max relative within each candidate's pool of 10 jobs (mapping the lowest score to 0.0 and highest score to 1.0), so a candidate whose best job matches few skills can still receive a high normalised score (e.g. 0.95+).*

| Candidate ID | Candidate Name | Candidate Family | Top-1 Job Title | Job Family | In Family? | Relevant? | Raw Overlap | Norm Score |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| SYN_DEMO_001 | Aarav Sharma | Data/AI | **Associate Machine Learning Engineer** | Data/AI | Yes | **Yes** | 3/5 (60.0%) | **0.9623** |
| SYN_DEMO_002 | Aditi Patel | Web/Software | **Backend Python Engineer** | Web/Software | Yes | **Yes** | 4/5 (80.0%) | **0.9872** |
| SYN_DEMO_003 | Vikram Reddy | Cybersecurity/Cloud | **Cloud Security Architect** | Cybersecurity/Cloud | Yes | **Yes** | 5/6 (83.3%) | **1.0000** |
| SYN_DEMO_004 | Ananya Deshmukh | Mobile/UI-UX | **Senior Android Engineer** | Mobile/UI-UX | Yes | **Yes** | 3/5 (60.0%) | **0.9517** |
| SYN_DEMO_005 | Rohan Mehta | Data/AI | **Senior Data Scientist** | Data/AI | Yes | **Yes** | 6/6 (100.0%) | **1.0000** |
| SYN_DEMO_006 | Pooja Nair | Web/Software | **Full Stack Developer** | Web/Software | Yes | **Yes** | 5/6 (83.3%) | **1.0000** |
| SYN_DEMO_007 | Siddharth Verma | Cybersecurity/Cloud | **DevOps & Cloud Engineer** | Web/Software | No | **No** | 1/6 (16.7%) | **0.8845** |
| SYN_DEMO_008 | Neha Kulkarni | Mobile/UI-UX | **Senior Android Engineer** | Mobile/UI-UX | Yes | **Yes** | 5/5 (100.0%) | **1.0000** |
| SYN_DEMO_009 | Kavya Iyer | Data/AI | **Associate Machine Learning Engineer** | Data/AI | Yes | **Yes** | 3/5 (60.0%) | **0.9376** |
| SYN_DEMO_010 | Arjun Menon | Web/Software | **Full Stack Developer** | Web/Software | Yes | **Yes** | 4/6 (66.7%) | **1.0000** |
| SYN_DEMO_011 | Priya Chopra | Cybersecurity/Cloud | **Cloud Security Architect** | Cybersecurity/Cloud | Yes | **Yes** | 5/6 (83.3%) | **1.0000** |
| SYN_DEMO_012 | Rahul Sen | Mobile/UI-UX | **Senior Android Engineer** | Mobile/UI-UX | Yes | **Yes** | 5/5 (100.0%) | **1.0000** |
| SYN_DEMO_013 | Tanvi Naidu | Data/AI | **Associate Machine Learning Engineer** | Data/AI | Yes | **Yes** | 2/5 (40.0%) | **0.9414** |
| SYN_DEMO_014 | Kunal Bose | Web/Software | **Full Stack Developer** | Web/Software | Yes | **Yes** | 5/6 (83.3%) | **0.9936** |
| SYN_DEMO_015 | Divya Hegde | Cybersecurity/Cloud | **Cloud Security Architect** | Cybersecurity/Cloud | Yes | **Yes** | 5/6 (83.3%) | **1.0000** |
| SYN_DEMO_016 | Akash Rao | Mobile/UI-UX | **Senior Android Engineer** | Mobile/UI-UX | Yes | **Yes** | 2/5 (40.0%) | **0.9782** |
| SYN_DEMO_017 | Sneha Joshi | Data/AI | **Associate Machine Learning Engineer** | Data/AI | Yes | **Yes** | 3/5 (60.0%) | **0.9489** |
| SYN_DEMO_018 | Varun Bhat | Web/Software | **Full Stack Developer** | Web/Software | Yes | **Yes** | 6/6 (100.0%) | **1.0000** |
| SYN_DEMO_019 | Meera Pillai | Cybersecurity/Cloud | **Cloud Security Architect** | Cybersecurity/Cloud | Yes | **Yes** | 4/6 (66.7%) | **1.0000** |
| SYN_DEMO_020 | Tarun Gupta | Mobile/UI-UX | **Senior Android Engineer** | Mobile/UI-UX | Yes | **Yes** | 5/5 (100.0%) | **1.0000** |

### Recomputed Metrics from Per-Candidate View (Item 6b Verification):
- **Candidates with In-Family Top-1 Match**: **19 of 20** (95.0%)
- **Top-1 Precision (P@1)**: **95.0%** (19/20 candidates received an in-family relevant job as Rank 1) [Matches Table 3 exactly]
- **Top-2 Precision (P@2)**: **70.0%** (Macro average across top 2 recommendations) [Matches Table 3 exactly]

### Top Matches per Candidate (Representative Sample):

| Candidate ID | Candidate Name | Job ID | Job Title (Family) | Match Score | Matched Skills | Missing Skills | Exp Matched | Alignment | Relevance |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: | :---: |
| SYN_DEMO_001 | Aarav Sharma | JOB_DEMO_002 | **Associate Machine Learning Engineer** (Data/AI) | **0.9623** | `Machine Learning, Python, TensorFlow` | `Git, Pandas` | `Machine Learning, Python, TensorFlow` | Correct | Partial Fit |
| SYN_DEMO_001 | Aarav Sharma | JOB_DEMO_001 | **Senior Data Scientist** (Data/AI) | **0.7289** | `Machine Learning, PyTorch, Python, Scikit-Learn` | `Deep Learning, SQL` | `Machine Learning, PyTorch, Python, Scikit-Learn` | Correct | Partial Fit |
| SYN_DEMO_002 | Aditi Patel | JOB_DEMO_005 | **Backend Python Engineer** (Web/Software) | **0.9872** | `Docker, FastAPI, Python, REST APIs` | `PostgreSQL` | `Docker, FastAPI, Python, REST APIs` | Correct | Strong Fit |
| SYN_DEMO_002 | Aditi Patel | JOB_DEMO_004 | **Full Stack Developer** (Web/Software) | **0.9018** | `Git, Node.js, REST APIs, TypeScript` | `PostgreSQL, React` | `Git, Node.js, REST APIs, TypeScript` | Correct | Partial Fit |
| SYN_DEMO_003 | Vikram Reddy | JOB_DEMO_007 | **Cloud Security Architect** (Cybersecurity/Cloud) | **1.0000** | `AWS, IAM, Linux, Network Security, Terraform` | `Kubernetes` | `AWS, IAM, Linux, Network Security, Terraform` | Correct | Strong Fit |
| SYN_DEMO_003 | Vikram Reddy | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8136** | `CI/CD, Docker, Linux` | `Git, PostgreSQL, REST APIs` | `CI/CD, Docker, Linux` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_004 | Ananya Deshmukh | JOB_DEMO_009 | **Senior Android Engineer** (Mobile/UI-UX) | **0.9517** | `Git, Kotlin, REST APIs` | `Flutter, Mobile Design` | `Git, Kotlin, REST APIs` | Correct | Partial Fit |
| SYN_DEMO_004 | Ananya Deshmukh | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8641** | `Git, REST APIs` | `CI/CD, Docker, Linux, PostgreSQL` | `Git, REST APIs` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_005 | Rohan Mehta | JOB_DEMO_001 | **Senior Data Scientist** (Data/AI) | **1.0000** | `Deep Learning, Machine Learning, PyTorch, Python, SQL, Scikit-Learn` | `None` | `Deep Learning, Machine Learning, PyTorch, Python, SQL, Scikit-Learn` | Correct | Strong Fit |
| SYN_DEMO_005 | Rohan Mehta | JOB_DEMO_002 | **Associate Machine Learning Engineer** (Data/AI) | **0.9305** | `Machine Learning, Python, TensorFlow` | `Git, Pandas` | `Machine Learning, Python, TensorFlow` | Correct | Partial Fit |
| SYN_DEMO_006 | Pooja Nair | JOB_DEMO_004 | **Full Stack Developer** (Web/Software) | **1.0000** | `Git, Node.js, PostgreSQL, React, TypeScript` | `REST APIs` | `Git, Node.js, PostgreSQL, React, TypeScript` | Correct | Strong Fit |
| SYN_DEMO_006 | Pooja Nair | JOB_DEMO_005 | **Backend Python Engineer** (Web/Software) | **0.9132** | `Docker, FastAPI, PostgreSQL, Python` | `REST APIs` | `Docker, FastAPI, PostgreSQL, Python` | Correct | Strong Fit |
| SYN_DEMO_007 | Siddharth Verma | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8845** | `Docker` | `CI/CD, Git, Linux, PostgreSQL, REST APIs` | `Docker` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_007 | Siddharth Verma | JOB_DEMO_007 | **Cloud Security Architect** (Cybersecurity/Cloud) | **0.5695** | `IAM, Network Security, Terraform` | `AWS, Kubernetes, Linux` | `IAM, Network Security, Terraform` | Correct | Partial Fit |
| SYN_DEMO_008 | Neha Kulkarni | JOB_DEMO_009 | **Senior Android Engineer** (Mobile/UI-UX) | **1.0000** | `Flutter, Git, Kotlin, Mobile Design, REST APIs` | `None` | `Flutter, Git, Kotlin, Mobile Design, REST APIs` | Correct | Strong Fit |
| SYN_DEMO_008 | Neha Kulkarni | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8526** | `Git, REST APIs` | `CI/CD, Docker, Linux, PostgreSQL` | `Git, REST APIs` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_009 | Kavya Iyer | JOB_DEMO_002 | **Associate Machine Learning Engineer** (Data/AI) | **0.9376** | `Machine Learning, Pandas, TensorFlow` | `Git, Python` | `Machine Learning, Pandas, TensorFlow` | Correct | Partial Fit |
| SYN_DEMO_009 | Kavya Iyer | JOB_DEMO_001 | **Senior Data Scientist** (Data/AI) | **0.7333** | `Deep Learning, Machine Learning, PyTorch, SQL, Scikit-Learn` | `Python` | `Deep Learning, Machine Learning, PyTorch, SQL, Scikit-Learn` | Correct | Strong Fit |
| SYN_DEMO_010 | Arjun Menon | JOB_DEMO_004 | **Full Stack Developer** (Web/Software) | **1.0000** | `Git, Node.js, PostgreSQL, TypeScript` | `REST APIs, React` | `Git, Node.js, PostgreSQL, TypeScript` | Correct | Partial Fit |
| SYN_DEMO_010 | Arjun Menon | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.6144** | `Git, PostgreSQL` | `CI/CD, Docker, Linux, REST APIs` | `Git, PostgreSQL` | Correct | Not Relevant |
| SYN_DEMO_011 | Priya Chopra | JOB_DEMO_007 | **Cloud Security Architect** (Cybersecurity/Cloud) | **1.0000** | `IAM, Kubernetes, Linux, Network Security, Terraform` | `AWS` | `IAM, Kubernetes, Linux, Network Security, Terraform` | Correct | Strong Fit |
| SYN_DEMO_011 | Priya Chopra | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8737** | `CI/CD, Docker, Linux` | `Git, PostgreSQL, REST APIs` | `CI/CD, Docker, Linux` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_012 | Rahul Sen | JOB_DEMO_009 | **Senior Android Engineer** (Mobile/UI-UX) | **1.0000** | `Flutter, Git, Kotlin, Mobile Design, REST APIs` | `None` | `Flutter, Git, Kotlin, Mobile Design, REST APIs` | Correct | Strong Fit |
| SYN_DEMO_012 | Rahul Sen | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8426** | `Git, REST APIs` | `CI/CD, Docker, Linux, PostgreSQL` | `Git, REST APIs` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_013 | Tanvi Naidu | JOB_DEMO_002 | **Associate Machine Learning Engineer** (Data/AI) | **0.9414** | `Pandas, TensorFlow` | `Git, Machine Learning, Python` | `Pandas, TensorFlow` | Correct | Partial Fit |
| SYN_DEMO_013 | Tanvi Naidu | JOB_DEMO_001 | **Senior Data Scientist** (Data/AI) | **0.4667** | `Deep Learning, PyTorch` | `Machine Learning, Python, SQL, Scikit-Learn` | `Deep Learning, PyTorch` | Correct | Not Relevant |
| SYN_DEMO_014 | Kunal Bose | JOB_DEMO_004 | **Full Stack Developer** (Web/Software) | **0.9936** | `Git, PostgreSQL, REST APIs, React, TypeScript` | `Node.js` | `Git, PostgreSQL, REST APIs, React, TypeScript` | Correct | Strong Fit |
| SYN_DEMO_014 | Kunal Bose | JOB_DEMO_005 | **Backend Python Engineer** (Web/Software) | **0.9080** | `Docker, FastAPI, PostgreSQL, REST APIs` | `Python` | `Docker, FastAPI, PostgreSQL, REST APIs` | Correct | Strong Fit |
| SYN_DEMO_015 | Divya Hegde | JOB_DEMO_007 | **Cloud Security Architect** (Cybersecurity/Cloud) | **1.0000** | `AWS, IAM, Kubernetes, Linux, Terraform` | `Network Security` | `AWS, IAM, Kubernetes, Linux, Terraform` | Correct | Strong Fit |
| SYN_DEMO_015 | Divya Hegde | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.6570** | `CI/CD, Docker, Linux` | `Git, PostgreSQL, REST APIs` | `CI/CD, Docker, Linux` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_016 | Akash Rao | JOB_DEMO_009 | **Senior Android Engineer** (Mobile/UI-UX) | **0.9782** | `Flutter, REST APIs` | `Git, Kotlin, Mobile Design` | `Flutter, REST APIs` | Correct | Partial Fit |
| SYN_DEMO_016 | Akash Rao | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8577** | `REST APIs` | `CI/CD, Docker, Git, Linux, PostgreSQL` | `REST APIs` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_017 | Sneha Joshi | JOB_DEMO_002 | **Associate Machine Learning Engineer** (Data/AI) | **0.9489** | `Machine Learning, Pandas, TensorFlow` | `Git, Python` | `Machine Learning, Pandas, TensorFlow` | Correct | Partial Fit |
| SYN_DEMO_017 | Sneha Joshi | JOB_DEMO_001 | **Senior Data Scientist** (Data/AI) | **0.7333** | `Deep Learning, Machine Learning, PyTorch, SQL, Scikit-Learn` | `Python` | `Deep Learning, Machine Learning, PyTorch, SQL, Scikit-Learn` | Correct | Strong Fit |
| SYN_DEMO_018 | Varun Bhat | JOB_DEMO_004 | **Full Stack Developer** (Web/Software) | **1.0000** | `Git, Node.js, PostgreSQL, REST APIs, React, TypeScript` | `None` | `Git, Node.js, PostgreSQL, REST APIs, React, TypeScript` | Correct | Strong Fit |
| SYN_DEMO_018 | Varun Bhat | JOB_DEMO_005 | **Backend Python Engineer** (Web/Software) | **0.9768** | `Docker, FastAPI, PostgreSQL, Python, REST APIs` | `None` | `Docker, FastAPI, PostgreSQL, Python, REST APIs` | Correct | Strong Fit |
| SYN_DEMO_019 | Meera Pillai | JOB_DEMO_007 | **Cloud Security Architect** (Cybersecurity/Cloud) | **1.0000** | `AWS, IAM, Kubernetes, Terraform` | `Linux, Network Security` | `AWS, IAM, Kubernetes, Terraform` | Correct | Partial Fit |
| SYN_DEMO_019 | Meera Pillai | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.4010** | `None` | `CI/CD, Docker, Git, Linux, PostgreSQL, REST APIs` | `None` | Correct | Not Relevant (Cross-Domain) |
| SYN_DEMO_020 | Tarun Gupta | JOB_DEMO_009 | **Senior Android Engineer** (Mobile/UI-UX) | **1.0000** | `Flutter, Git, Kotlin, Mobile Design, REST APIs` | `None` | `Flutter, Git, Kotlin, Mobile Design, REST APIs` | Correct | Strong Fit |
| SYN_DEMO_020 | Tarun Gupta | JOB_DEMO_006 | **DevOps & Cloud Engineer** (Web/Software) | **0.8484** | `Git, REST APIs` | `CI/CD, Docker, Linux, PostgreSQL` | `Git, REST APIs` | Correct | Not Relevant (Cross-Domain) |

### Summary Performance & Relevance Separation:
- **Average Score of Pairs Labelled Relevant**: **0.7659** (N=47 pairs)
- **Average Score of Pairs Labelled Not Relevant**: **0.2447** (N=153 pairs)
- **Discriminative Score Margin**: **+0.5212**
- **Top-1 Precision (P@1)**: **95.0%** (19/20 candidates received an in-family relevant job as Rank 1)
- **Top-2 Precision (P@2)**: **70.0%** (Macro average across top 2 recommendations)
- **Skill Attribution Quality**: In all 200 pairs, the matcher accurately decomposed required job skills into matched versus missing skills.
