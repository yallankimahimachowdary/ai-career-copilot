# AI Career Copilot — Frontend Build Tasks

## Phase 1: Foundation & Scaffold
- [x] Vite + React project scaffold
- [x] Install all npm dependencies (Tailwind v4, Lucide, Recharts, Router, Axios, Dropzone)
- [x] Tailwind CSS + PostCSS configuration
- [x] shadcn/ui primitives (button, card, badge, dialog, tabs, progress, input, textarea)
- [x] API client layer (Axios + resumeApi, jobApi, matchApi, coachApi, marketApi)
- [x] Mock data for offline development (`mockData.js`)
- [x] Layout components (Sidebar, Header, PageContainer)
- [x] React Router setup with 4 core routes
- [x] Production build verification (`npm run build` passing in 721ms)

## Phase 2: Resume Upload & Profile (Tab 1)
- [x] ResumeUploader (drag-and-drop dropzone, validation, loading states)
- [x] ResumeProfileCard (complete parsed profile, contact, experience timeline, projects, certs)
- [x] SkillBadges (automatic color-coded category mapping)
- [x] ResumeList (previously uploaded resumes, select & delete)
- [x] Integration with backend upload endpoint

## Phase 3: Job Matches & XAI (Tab 2)
- [x] MatchDashboard (filters: location, remote-only, min score slider)
- [x] JobMatchCard (fit index gauge, top skills preview, primary SHAP quote)
- [x] ScoreBreakdown (3-category progress bars for skills, experience, education)
- [x] SkillComparison (matched, critical must-have gaps, nice-to-have gaps)
- [x] ShapWaterfall (Recharts diverging horizontal bar chart for TreeSHAP attributions)
- [x] MatchDetailModal (deep-dive tabs + one-click transition to Interview Coach)

## Phase 4: Interview Coach (Tab 3)
- [x] CoachDashboard (target role selector + 3-step tabs)
- [x] SkillGapReport (diagnostic report, critical gaps, learning roadmap, readiness gauge)
- [x] QuestionBank (categorized technical, STAR behavioral, gap-probing cards with model answers)
- [x] MockInterview (interactive terminal practice interface with word count & timer)
- [x] AnswerEvaluator (0-10 score, grade badge, rubric breakdown progress bars, strengths/weaknesses)
- [x] ReadinessGauge (circular SVG progress gauge)

## Phase 5: Market Insights (Tab 4)
- [x] MarketDashboard (search by role/title and location, sub-tabs)
- [x] SalaryChart (5-number percentile spectrum: min, p25, median, p75, max + top employers)
- [x] TrendingSkills (horizontal bar chart with high/moderate/niche demand signals)
- [x] DemandHeatmap (geographic concentration, remote ratio, avg compensation)
- [x] RoleOverview (4 metric cards, engagement mix, leading employers, narrative)
- [x] ResumePositioning (candidate coverage gauge, alignment matrix table, positioning directives)

## Phase 6: Polish & Verification
- [x] Codebase compilation and zero build errors verified with `npm run build`
- [x] Offline fallback support seamlessly built into every tab
- [x] Responsive layout and dark SaaS styling
