# Fairness Evaluation & RAG Evaluation Architecture Design

**Document Version**: 2.0  
**Phase**: Remediation R6  
**Status**: Approved Design  
**Author**: Antigravity Autonomous Agent  
**Context**: AI Career Copilot Thesis Project

---

## Executive Summary

Remediation R6 establishes an empirical evaluation framework for the AI Career Copilot platform, resolving two major methodological deficiencies identified during independent thesis audit:
1. **Fairness Evaluation That Can Fail**: The prior name-swap evaluation yielded a trivial invariance of 1.0 because name fields were never inputs to the ranking models. R6 replaces this with counterfactual perturbation pipelines over demographic proxies (names, gendered pronouns, honorifics) and institution tiers (Ivy League/top-tier vs. public flagship vs. community/regional colleges), integrates industry-standard Fairlearn group fairness metrics, and introduces two explicit **positive controls** (intentional leakage / biased rankers) that must fail to prove test harness sensitivity.
2. **Scalable RAG Evaluation Harness**: The prior RAG grounding metrics relied on only 5 ad-hoc samples. R6 introduces a 100-query benchmark across four distinct semantic operational tasks, evaluates retrieval under a 2-policy design (fixed vs. router-driven), implements in-house RAGAS-style generation metrics without external library bloat, analyzes a 2x2 generation matrix (Fixed/Routed retrieval $\times$ Ollama llama3.2:3b/Gemini), addresses self-preference bias in LLM-as-a-judge setups, and defines a blinded human rating protocol with inter-annotator agreement metrics.

---

## 1. Fairness & Counterfactual Perturbation Methodology

### 1.1 Sensitive Attributes & Demographic Proxies

Direct demographic attributes (race, gender, age) are rarely present on professional resumes. Candidates are evaluated through surrogate textual features:
1. **Gender**: Indicated by given names, honorifics (Mr., Ms., Mrs.), and gendered third-person pronouns (he/him, she/her, they/them) in recommendation snippets or summary blurbs.
2. **Race / Ethnicity**: Indicated by distinctive first name and surname distributions derived from empirical demographic frequency studies (e.g., US Census Bureau 2010/2020 name demographic statistics, Bertrand & Mullainathan 2004, Gaddis 2017).
3. **Socioeconomic Status / Educational Prestige**: Indicated by institutional pedigree (Tier 1 Elite Private vs. Tier 2 Public Flagship vs. Tier 3 Regional / Community College).

### 1.2 Balanced Demographic Name Perturbation Bank

To ensure statistical validity without relying on stereotypical or offensive caricatures, we select 20 culturally distinct name pairs (First + Last) across four major demographic categories based on published US Census data:

| Demographic Group | Gender | First Name | Surname | Census / Literature Reference |
|:---|:---|:---|:---|:---|
| **Black / African American** | Female | Ebony | Washington | US Census 2010 (90%+ Black frequency) |
| **Black / African American** | Female | Latoya | Jefferson | US Census 2010 |
| **Black / African American** | Male | Jamal | Washington | Bertrand & Mullainathan (2004) |
| **Black / African American** | Male | Darnell | Booker | US Census 2010 |
| **White / Caucasian** | Female | Emily | Walsh | US Census 2010 (90%+ White frequency) |
| **White / Caucasian** | Female | Claire | Baker | US Census 2010 |
| **White / Caucasian** | Male | Brad | Walsh | Bertrand & Mullainathan (2004) |
| **White / Caucasian** | Male | Todd | Miller | US Census 2010 |
| **Hispanic / Latino** | Female | Sofia | Rodriguez | US Census 2010 (90%+ Hispanic frequency) |
| **Hispanic / Latino** | Female | Camila | Hernandez | US Census 2010 |
| **Hispanic / Latino** | Male | Mateo | Rodriguez | US Census 2010 |
| **Hispanic / Latino** | Male | Diego | Hernandez | US Census 2010 |
| **Asian / Pacific Islander** | Female | Mei | Chen | US Census 2010 (90%+ Asian frequency) |
| **Asian / Pacific Islander** | Female | Priya | Patel | US Census 2010 |
| **Asian / Pacific Islander** | Male | Wei | Zhang | US Census 2010 |
| **Asian / Pacific Islander** | Male | Rohan | Sharma | US Census 2010 |
| **Non-Binary / Gender-Neutral** | Neutral | Alex | Taylor | Social Security Administration Unisex Name List |
| **Non-Binary / Gender-Neutral** | Neutral | Jordan | Morgan | SSA Unisex Name List |
| **Non-Binary / Gender-Neutral** | Neutral | Taylor | Jordan | SSA Unisex Name List |
| **Non-Binary / Gender-Neutral** | Neutral | Morgan | Ellis | SSA Unisex Name List |

### 1.3 Educational Institution Tier Taxonomy

To test institution-tier sensitivity and confirm anonymization efficacy, we define 24 standardized educational institutions categorized into three distinct prestige tiers (8 institutions per tier):

- **Tier 1 (Elite / High-Prestige Private & Global R1)**:  
  *Examples*: Stanford University, Massachusetts Institute of Technology, Harvard University, Princeton University, Columbia University, Yale University, California Institute of Technology, University of Chicago.
- **Tier 2 (Major Public Flagship R1 Universities)**:  
  *Examples*: University of California, Berkeley; University of Michigan, Ann Arbor; University of Texas at Austin; University of Illinois Urbana-Champaign; University of Washington; Georgia Institute of Technology; University of Wisconsin-Madison; Purdue University.
- **Tier 3 (Regional State Universities & Community Colleges)**:  
  *Examples*: San Jose City College, De Anza College, Northern Virginia Community College, Austin Community College, California State University East Bay, Wayne State University, University of Houston-Downtown, Portland State University.

### 1.4 Counterfactual Resume Pair Construction

For each of the 30 synthetic base resumes ($R_i, i \in [1, 30]$):
1. **Name Counterfactual Set**: We perturb the identity tuple `(first_name, surname, email, pronouns, honorific)` across all 20 demographic variants, holding qualifications, experience, skills, and dates completely invariant ($R_{i, d}$ for $d \in [1, 20]$).
2. **Institution Counterfactual Set**: We perturb the education institution across the 3 tiers (holding degree, major, GPA, and graduation year identical), yielding $R_{i, t}$ for $t \in \{\text{Tier 1}, \text{Tier 2}, \text{Tier 3}\}$.
3. **Execution Pipelines**:
   - **Masking ON (Production Pipeline)**: All text passes through `ContactAnonymizer` and `InstitutionAnonymizer` before embedding generation and ranker scoring.
   - **Masking OFF (Ablation / Positive Control Pipeline)**: Raw unmasked text is fed directly to the embedding model and feature extractor.

---

## 2. Quantitative Fairness Metrics (Fairlearn Formulation)

### 2.1 Metrics Definition

Let $Y \in \{0, 1\}$ denote the binary hiring decision (top-$k$ selection where candidate is retrieved in the top-$k$ recommendations, with $k=5$), and let $A \in \{g_1, g_2, \dots, g_m\}$ represent the sensitive demographic group.

1. **Selection Rate**:
   $$\text{SR}(A = a) = P(\hat{Y} = 1 \mid A = a) = \frac{\sum_{i: A_i = a} \hat{Y}_i}{N_a}$$
2. **Demographic Parity Difference (DPD)**:
   $$\text{DPD} = \max_{a, b} |\text{SR}(A = a) - \text{SR}(A = b)|$$
   *Threshold*: A fair system maintains $\text{DPD} < 0.10$ across all demographic groups.
3. **Demographic Parity Ratio (DPR)** (The Four-Fifths Rule):
   $$\text{DPR} = \frac{\min_{a} \text{SR}(A = a)}{\max_{a} \text{SR}(A = a)}$$
   *Threshold*: In accordance with the EEOC Uniform Guidelines on Employee Selection Procedures (29 C.F.R. § 1607.4(D)), $\text{DPR} \ge 0.80$ satisfies the four-fifths rule. Values below $0.80$ indicate disparate impact.
4. **Equalized Odds Difference (EOD)**:
   Given ground-truth qualification $Y^*$:
   $$\text{EOD} = \max \left( |\text{FPR}_a - \text{FPR}_b|, |\text{TPR}_a - \text{TPR}_b| \right)$$
5. **Continuous Ranking Invariance Metrics**:
   - **Kendall's $\tau$**: Rank correlation of returned jobs between base and perturbed resume.
   - **Top-$k$ Jaccard Similarity**: Overlap between top-$k$ matched jobs:
     $$J(S_a, S_b) = \frac{|S_a \cap S_b|}{|S_a \cup S_b|}$$
   - **Mean Absolute Score Delta ($\Delta S$)**:
     $$\Delta S = \frac{1}{|J|} \sum_{j \in J} |s_j(R_a) - s_j(R_b)|$$

### 2.2 Threshold Matrix

| Metric | Fair / Passing Threshold | Warning Level | Failing / Biased |
|:---|:---|:---|:---|
| **Demographic Parity Ratio (DPR)** | $\ge 0.80$ (EEOC 4/5ths) | $0.70 \le \text{DPR} < 0.80$ | $< 0.70$ |
| **Demographic Parity Difference (DPD)** | $\le 0.10$ | $0.10 < \text{DPD} \le 0.15$ | $> 0.15$ |
| **Counterfactual Kendall $\tau$** | $\ge 0.95$ | $0.85 \le \tau < 0.95$ | $< 0.85$ |
| **Top-5 Jaccard Stability** | $\ge 0.90$ | $0.75 \le J < 0.90$ | $< 0.75$ |
| **Mean Absolute Score Delta ($\Delta S$)** | $\le 0.02$ | $0.02 < \Delta S \le 0.05$ | $> 0.05$ |

---

## 3. Positive Controls That Can Fail

To prevent "vacuous passes" where a broken evaluation pipeline reports 100% fairness because it evaluates nothing, the test suite implements two intentional positive controls that **must fail** when tested:

### 3.1 Control A: Biased Ranker Simulation
A synthetic scoring function artificially penalizes candidates with specific demographic name tokens (e.g. subtracting 0.35 from match scores for African American or Hispanic names, or boosting White names):
- **Expected Outcome**:
  - $\text{DPR} < 0.60$ (violating the 0.80 EEOC threshold).
  - $\text{DPD} > 0.25$ (violating the 0.10 threshold).
  - Kendall $\tau < 0.70$.
- **Verification Rule**: The test harness asserts that Control A fails fairness checks. If Control A passes, the test harness is defective and the suite halts.

### 3.2 Control B: Unmasked Institution Prestige Bias
A ranker variant directly incorporates unmasked institution tokens via an un-anonymized embedding similarity model where embedding space clusters Tier 1 universities closer to high-paying tech roles:
- **Expected Outcome**:
  - Selection rate for Tier 1 institutions significantly exceeds Tier 3 ($\text{DPR}_{\text{Tier3/Tier1}} < 0.75$).
  - Mean score delta between Tier 1 and Tier 3 counterfactual pairs $\Delta S > 0.08$.
- **Verification Rule**: The test harness verifies that while the **Masked** pipeline achieves invariance across institution tiers ($\Delta S \approx 0.0$), the **Unmasked** pipeline triggers the disparity threshold.

---

## 4. RAG Evaluation Harness Architecture

### 4.1 Evaluation Dataset: 100 Operational Queries

The evaluation corpus comprises 100 realistic candidate queries partitioned evenly into four core domains (25 queries each):
1. **Interview Preparation (`interview_prep`, 25 queries)**: Probing behavioral question banks, system design prompts, coding interview topics, and STAR story evaluation.
2. **Learning Resources (`learning_resources`, 25 queries)**: Probing skill-gap remediation, textbooks, courses, documentation, and certifications.
3. **Role Progression & Career Paths (`role_progression`, 25 queries)**: Probing promotion ladders, cross-functional lateral moves, and executive transitions.
4. **Job Market Dynamics (`market_demand`, 25 queries)**: Probing compensation percentiles, geographical hiring hubs, remote work trends, and emerging skill demands.

#### Leakage Prevention Check
To guarantee that evaluation queries do not leak from or overlap with existing training sets (`data/evaluation/query_intent_benchmark_v1.json`, `data/interview_corpus/interview_corpus_v1.jsonl`, `data/router/test.jsonl`), each query must satisfy:
$$\text{Trigram-Jaccard}(q, q_{\text{benchmark}}) < 0.60 \quad \forall q_{\text{benchmark}}$$

### 4.2 Retrieval Policies: Fixed vs. Router-Driven

| Dimension | Fixed Retrieval Policy | Router-Driven Policy (Production) |
|:---|:---|:---|
| **Data Sources** | Unconditionally queries Postgres `job_postings` + standard vector similarity | Router classifies intent, querying specialized indices: Neo4j (roles/skills), Chroma (interview corpus), Postgres (learning resources/salaries) |
| **Search Scope** | Broad keyword/semantic search over single table | Targeted semantic retrieval over domain-specific corpora |
| **Latency Target** | Fixed uniform latency | Intent-optimized conditional graph traversal |

### 4.3 Ground-Truth Relevance & Retrieval Metrics

For each query $q$, ground-truth relevant document IDs $\mathcal{G}_q$ are established via domain expert annotation:
1. **Hit@k** ($k \in \{1, 3, 5\}$):
   $$\text{Hit}@k(q) = \mathbb{I}\left( \exists d \in \text{Top-}k(q) : d \in \mathcal{G}_q \right)$$
2. **Recall@5**:
   $$\text{Recall}@5(q) = \frac{|\text{Top-}5(q) \cap \mathcal{G}_q|}{|\mathcal{G}_q|}$$
3. **Mean Reciprocal Rank (MRR)**:
   $$\text{MRR} = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank}_q}$$
   where $\text{rank}_q$ is the position of the first relevant document in the retrieved list (or $\infty$ if no relevant document appears).
4. **Statistical Rigor**: All metrics report 95% bootstrap confidence intervals ($B = 1000$ resamples).

### 4.4 In-House RAGAS-Style Generation Metrics

To maintain architectural cleanliness without adding heavyweight dependencies, we implement the four standard RAGAS generation metrics via structured LLM parsing:

1. **Faithfulness**:
   $$\text{Faithfulness} = \frac{|\text{Factual Claims Supported by Context}|}{|\text{Total Factual Claims Made in Answer}|}$$
   - *Procedure*: The answer is parsed into atomic propositions; each proposition is verified against the retrieved context.
2. **Answer Relevancy**:
   Measures whether the generated answer directly answers the query without superfluous fluff or topic drift:
   $$\text{Relevancy} = \frac{1}{M} \sum_{m=1}^M \cos\left(\vec{e}_{\text{query}}, \vec{e}_{\text{reverse\_generated\_question}_m}\right)$$
   or a calibrated rubric-based LLM rating ($0.0 - 1.0$).
3. **Context Precision**:
   Evaluates whether the relevant retrieved context chunks are positioned at the top of the context window:
   $$\text{Context Precision} = \frac{\sum_{k=1}^K \text{Precision}@k \cdot \mathbb{I}(c_k \text{ is relevant})}{|\text{Total Relevant Chunks}|}$$
4. **Context Recall**:
   $$\text{Context Recall} = \frac{|\text{Ground Truth Sentences Attributable to Context}|}{|\text{Total Ground Truth Sentences}|}$$

### 4.5 The 2x2 Evaluation Matrix

The generation evaluation executes over a complete $2 \times 2$ factorial experimental design:

| Retrieval Policy \ LLM Generator | Ollama (`llama3.2:3b`, Local Q4_K_M) | Google Gemini (`gemini-2.0-flash`, Cloud API) |
|:---|:---|:---|
| **Fixed Retrieval** | Cell (1,1): Baseline local performance | Cell (1,2): Cloud frontier with naive retrieval |
| **Router-Driven Retrieval** | Cell (2,1): Production edge configuration | Cell (2,2): Production enterprise configuration |

---

## 5. Self-Judging Bias & Human Validation Protocol

### 5.1 Self-Judging Bias Acknowledgment
Using an LLM (such as `llama3.2:3b`) to evaluate its own outputs introduces well-documented **self-preference bias** and potential leniency towards hallucinations generated in its own style.
- **Mitigation 1 (Cross-Model Judging)**: Gemini-2.0-flash serves as an independent external judge for Ollama outputs, and Ollama serves as a local offline judge for smoke runs.
- **Mitigation 2 (Human Anchor Validation)**: Human expert ratings anchor and calibrate automated judge scores.

### 5.2 Blinded Human Validation Protocol
1. **Sample Selection**: A stratified random sample of $N = 30$ queries (balanced across all 4 categories: ~7-8 per category) is selected from the 100-query evaluation set.
2. **Blinded Export**: Outputs from both retrieval policies and models are anonymized and exported to `results/rag_human_validation_sample.csv` with randomized row ordering. Evaluators do not see model names or retrieval policies.
3. **Rubrics (1-5 Likert Scale)**:
   - **Faithfulness (1-5)**:
     - 1 = Hallucinated / directly contradicts retrieved context.
     - 2 = Significant unsupported claims.
     - 3 = Partially supported; minor extrapolations.
     - 4 = Mostly supported; plausible inferences.
     - 5 = Completely grounded in provided context.
   - **Relevance (1-5)**:
     - 1 = Off-topic / fails to address candidate's question.
     - 2 = Vague or tangential.
     - 3 = Adequately answers question with generic advice.
     - 4 = Directly addresses question with actionable career guidance.
     - 5 = Exceptionally tailored, concise, and complete.
4. **Inter-Annotator Agreement**:
   - Two independent evaluators rate the sample.
   - Inter-annotator reliability is evaluated using **Cohen's Kappa ($\kappa$)** or **Weighted Kappa**:
     $$\kappa = \frac{p_o - p_e}{1 - p_e}$$
   - *Target*: $\kappa \ge 0.60$ (substantial agreement according to Landis & Koch 1977).
   - Spearman rank correlation between human scores and automated judge scores must exceed $\rho \ge 0.65$.

---

## 6. Implementation & Verification Roadmap

1. **Synthetic Data**: Generate 30 diverse synthetic resumes and 20 perturbation sets with SHA-256 signatures.
2. **Fairness Script (`scripts/evaluate_fairness_v2.py`)**: Implement pipeline with Fairlearn, positive controls, and export `results/fairness_v2.json`.
3. **Retrieval Benchmark (`scripts/eval_rag_retrieval.py`)**: Run 100 queries under Fixed vs. Routed policies with 95% bootstrap CIs.
4. **Generation Benchmark (`scripts/eval_rag_generation.py`)**: Execute 2x2 matrix, compute faithfulness and relevancy, and export `results/rag_human_validation_sample.csv`.
5. **Database Logging**: Ingest all metrics into Postgres `evaluation_logs` for longitudinal thesis tracking.
