# Table 2: Resume Parsing & Canonical Skill Extraction Evaluation

> **SYNTHETIC BENCHMARK -- Generated programmatically for college project evaluation.**
> **Dataset Storage Paths**:
> - Synthetic Resume Texts: `C:\Users\mahim\Projects\ai-career-copilot\data\college_demo\resumes` (`SYN_DEMO_001.txt` .. `SYN_DEMO_020.txt`)
> - Expected Ground Truth : `C:\Users\mahim\Projects\ai-career-copilot\data\college_demo\ground_truth.json`
> - **Evaluation Mode**: Evaluated on raw text strings using `parser_agent._parse_with_rules(raw_text)` with Taxonomy v2.1.

### Metric Definitions (One Line Each):
- **Coverage**: Proportion of ground-truth expected skill tokens that match at least one regex pattern in Taxonomy v2.1.
- **Canonical Recall**: Proportion of mapped expected canonical skills successfully extracted from the resume text by `parser_agent._parse_with_rules`.
- **Domain Precision**: Proportion of extracted domain-specific canonical skills that match expected ground truth, isolating generic workflow terms into a dedicated column.
- **Overall Precision**: Proportion of all extracted canonical skills (including generic workflow terms) that match expected ground truth.

| Candidate ID | Candidate Name | Role Family | Name | Degree | Inst | Coverage | Canonical Recall | Domain Prec | Overall Prec | Generic Terms Extracted |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| SYN_DEMO_001 | Aarav Sharma | Data/AI | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 33.3% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_002 | Aditi Patel | Web/Software | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 72.7% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_003 | Vikram Reddy | Cybersecurity/Cloud | 100% | 100% | 100% | 55.6% | **100.0%** | 100.0% | 62.5% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_004 | Ananya Deshmukh | Mobile/UI-UX | 100% | 100% | 100% | 50.0% | **100.0%** | 100.0% | 50.0% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_005 | Rohan Mehta | Data/AI | 100% | 100% | 100% | 87.5% | **100.0%** | 100.0% | 42.9% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_006 | Pooja Nair | Web/Software | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 75.0% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_007 | Siddharth Verma | Cybersecurity/Cloud | 100% | 100% | 100% | 33.3% | **100.0%** | 100.0% | 33.3% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_008 | Neha Kulkarni | Mobile/UI-UX | 100% | 100% | 100% | 37.5% | **100.0%** | 100.0% | 50.0% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_009 | Kavya Iyer | Data/AI | 100% | 100% | 100% | 88.9% | **100.0%** | 100.0% | 42.9% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_010 | Arjun Menon | Web/Software | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 66.7% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_011 | Priya Chopra | Cybersecurity/Cloud | 100% | 100% | 100% | 62.5% | **100.0%** | 100.0% | 62.5% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_012 | Rahul Sen | Mobile/UI-UX | 100% | 100% | 100% | 44.4% | **100.0%** | 100.0% | 57.1% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_013 | Tanvi Naidu | Data/AI | 100% | 100% | 100% | 83.3% | **100.0%** | 100.0% | 33.3% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_014 | Kunal Bose | Web/Software | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 72.7% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_015 | Divya Hegde | Cybersecurity/Cloud | 100% | 100% | 100% | 66.7% | **100.0%** | 100.0% | 66.7% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_016 | Akash Rao | Mobile/UI-UX | 100% | 100% | 100% | 50.0% | **100.0%** | 100.0% | 42.9% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_017 | Sneha Joshi | Data/AI | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 42.9% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_018 | Varun Bhat | Web/Software | 100% | 100% | 100% | 100.0% | **100.0%** | 100.0% | 76.9% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_019 | Meera Pillai | Cybersecurity/Cloud | 100% | 100% | 100% | 50.0% | **100.0%** | 100.0% | 42.9% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| SYN_DEMO_020 | Tarun Gupta | Mobile/UI-UX | 100% | 100% | 100% | 37.5% | **100.0%** | 100.0% | 50.0% | `Agile/Scrum, CI/CD, Git/GitHub, Software Engineering` |
| **MACRO AVERAGE** | **All 20 Profiles** | **4 Families** | **100.0%** | **100.0%** | **100.0%** | **72.4%** | **100.0%** | **100.0%** | **53.9%** | - |

### Per-Family Breakdown:
- **Cybersecurity/Cloud** (N=5): Expected Tokens = 38, Covered = 21 (55.3%), Not Covered = 17 (`Cryptography, Firewalls, IAM, Network Security`); Canonical Recall = **100.0%**, Domain Precision = **100.0%**, Overall Precision = **53.6%**
- **Data/AI** (N=5): Expected Tokens = 37, Covered = 34 (91.9%), Not Covered = 3 (`Data Visualization`); Canonical Recall = **100.0%**, Domain Precision = **100.0%**, Overall Precision = **39.0%**
- **Mobile/UI-UX** (N=5): Expected Tokens = 37, Covered = 16 (43.2%), Not Covered = 21 (`Flutter, Kotlin, Mobile Design, Swift, UI/UX Design, Wireframing`); Canonical Recall = **100.0%**, Domain Precision = **100.0%**, Overall Precision = **50.0%**
- **Web/Software** (N=5): Expected Tokens = 40, Covered = 40 (100.0%), Not Covered = 0 (`None`); Canonical Recall = **100.0%**, Domain Precision = **100.0%**, Overall Precision = **72.8%**

### Diagnostic Re-Runs (Item 1c):
- **SYN_DEMO_013** (Data/AI):
  - Expected Raw: `['Data Visualization', 'Deep Learning', 'NLP', 'Pandas', 'PyTorch', 'TensorFlow']`
  - Mapped Expected Canonical: `['Data Science', 'Machine Learning']` (5 of 6 expected tokens map to canonical taxonomy categories; `Data Visualization` is not covered)
  - Extracted by Parser: `['Agile/Scrum', 'CI/CD', 'Data Science', 'Git/GitHub', 'Machine Learning', 'Software Engineering']`
  - Result: **100.0% Canonical Recall** (`Data Science` and `Machine Learning` both recovered); Generic terms extracted: `Agile/Scrum`, `CI/CD`, `Git/GitHub`, `Software Engineering`.
- **SYN_DEMO_020** (Mobile/UI-UX):
  - Expected Raw: `['Flutter', 'Git', 'Kotlin', 'Mobile Design', 'REST APIs', 'React Native', 'Swift', 'Wireframing']`
  - Mapped Expected Canonical: `['Git/GitHub', 'REST API', 'React']` (3 of 8 expected tokens map to canonical taxonomy categories; `Flutter`, `Kotlin`, `Mobile Design`, `Swift`, `Wireframing` are not covered)
  - Extracted by Parser: `['Agile/Scrum', 'CI/CD', 'Git/GitHub', 'REST API', 'React', 'Software Engineering']`
  - Result: **100.0% Canonical Recall** (`Git/GitHub`, `REST API`, and `React` all recovered); Generic terms extracted: `Agile/Scrum`, `CI/CD`, `Software Engineering`.

### Key Observations Generated from Computed Totals (Table 2 Notes):
1. **Section Parsing Methodology**: Contact names, degrees, and institutions sit on fixed lines of the synthetic resume template and achieve 100.0% extraction via regular expressions in `parser_agent._parse_with_rules(raw_text)`.
2. **Broad Taxonomy Category Representation**: The canonical taxonomy maps several concrete tool names into umbrella categories (e.g. `PyTorch`, `TensorFlow`, `Keras`, `NLP`, and `Deep Learning` all map to `Machine Learning`; `Pandas`, `NumPy`, and `Spark` map to `Data Science`). While this facilitates role-level matching, it does not distinguish specific framework variations in the extracted profile.
3. **Taxonomy Coverage**: Across all 20 synthetic resumes (152 total expected skill tokens), 111 tokens (73.0%) match at least one pattern in Taxonomy v2.1. The remaining 41 tokens belong to specialized mobile, cloud, and security tools not indexed in the frozen taxonomy.
4. **Canonical Recall & Domain Precision (100% by Construction)**: Canonical recall (100.0%) and domain precision (100.0%) are 100% by construction because expected skills are mapped through the identical taxonomy patterns the parser applies to the resume text that contains them.
5. **Informative Metrics**: Consequently, taxonomy coverage (73.0% token coverage / 72.4% macro coverage) and overall precision (53.9%), which accounts for generic engineering workflow terms (Agile/Scrum, CI/CD, Git/GitHub, Software Engineering), are the informative numbers measuring dictionary completeness and extraction specificity.
6. **Stage 2 Rule Parser Latency Diagnosis**: Timing measurements show that initial invocation of `_parse_with_rules` requires ~4.2 - 5.4 s due to cold-start lazy initialization of the spaCy `en_core_web_sm` model and pattern compilation. Subsequent warm calls execute in under 70 ms (< 0.1 s). Zero retry backoffs occurred.
