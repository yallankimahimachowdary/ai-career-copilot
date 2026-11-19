# Table 1: Synthetic Evaluation Dataset Description

> **SYNTHETIC BENCHMARK -- Generated programmatically for college project evaluation.**
> *Relevance is defined by the generator's explicit rule and the matcher also uses skills, so the scores show consistent behaviour on synthetic data, not accuracy on real candidates.*

| Dataset Metric / Dimension | Value / Count | Description & Domain Scope |
| :--- | :---: | :--- |
| Total Synthetic Resumes | 20 | 4 Role Families (5 per family) |
| Total Synthetic Job Descriptions | 10 | 4 Role Families (2-3 per family) |
| Seniority Breakdown (Resumes) | Junior: 7, Mid: 7, Senior: 6 | Balanced Career Experience Spectrum |
| Role Family: Data/AI | 5 Resumes, 3 Jobs | Data Science, ML, AI Engineering |
| Role Family: Web/Software | 5 Resumes, 3 Jobs | Frontend, Backend, DevOps, Full-Stack |
| Role Family: Cybersecurity/Cloud | 5 Resumes, 2 Jobs | Cloud Architecture, DevSecOps, InfoSec |
| Role Family: Mobile/UI-UX | 5 Resumes, 2 Jobs | Android, iOS, UI/UX Product Design |
| Average Skills per Resume | 7.6 | Extracted from standardized technical skill pools |
| Average Skills per Job Description | 5.2 | Explicit core technical requirements |
| Total Evaluated Pairs | 200 | Full Cartesian Product (20 x 10) |
| Relevance: Strong Fit (rel=2) | 24 pairs (12.0%) | Same domain and >=70% required skill overlap |
| Relevance: Partial Fit (rel=1) | 23 pairs (11.5%) | Same domain and 40-69% required skill overlap |
| Relevance: Not Relevant (rel=0) | 153 pairs (76.5%) | Cross-domain family or <40% skill overlap |
