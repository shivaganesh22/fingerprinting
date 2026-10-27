# Weekly Supervision Progress Report Template (`reports/supervision_report_template.md`)

Use this template to prepare your weekly progress submission for your academic supervisor. Submit this document **at least 24 hours prior** to your scheduled supervision meeting.

---

## Weekly Progress Report

**Student Name:** [Your Name]  
**Supervisor Name:** [Supervisor Name]  
**Degree Programme:** MSc in Computing / Computer Science  
**Dissertation Title:** Measuring Browser Fingerprinting Prevalence and the Effectiveness of Privacy Countermeasures  
**Meeting Date:** [DD/MM/YYYY]  
**Meeting Time:** [HH:MM]  
**Project Week Number:** Week [X] of [Total Weeks]  

---

### 1. Progress Completed Since Last Meeting (What was Done)
- [x] **Pipeline / Implementation:**
  - *Example:* Completed automated test suite reaching 87.4% test coverage across all core modules.
  - *Example:* Verified all condition canaries (`fpstudy selfcheck`) passing on Chromium.
  - *Example:* Finished Tranco top 1,000 baseline and blocklist comparative crawl.
- [x] **Data Analysis & Evidence:**
  - *Example:* Derived classifications and generated paired McNemar contingency tables.
  - *Example:* Exported vector-specific Wilson 95% confidence intervals and LaTeX summary tables.
- [x] **Writing / Dissertation Drafting:**
  - *Example:* Completed initial draft of Chapter 3 (Methodology) and Chapter 4 (Implementation).
  - *Example:* Annotated 20 sample scripts in `data/labelled/labels.csv` for detector validation.

---

### 2. Objectives for Next Week (What will be Done)
- [ ] **Objective 1:** [e.g., Complete uBlock Origin crawl over the top 1,000 domains].
- [ ] **Objective 2:** [e.g., Draft Chapter 5 (Results) incorporating matplotlib prevalence figures].
- [ ] **Objective 3:** [e.g., Verify 5 candidate literature citations in `reports/literature_review_leads.md`].

---

### 3. Current Blockers & Challenges (Where Help is Needed)
- **Technical Blockers:** [e.g., Encountered Cloudflare challenge screens on 18 sites under baseline condition; verified neutrally classified under failure taxonomy].
- **Methodological Questions:** [e.g., Discussing whether to apply Bonferroni vs Holm-Bonferroni correction for vector sub-comparisons].
- **Resource Constraints:** [e.g., Overnight crawl duration on laptop battery vs university workstation].

---

### 4. Identified Project Risks & Mitigation Strategy
| Risk Description | Severity (L/M/H) | Likelihood (L/M/H) | Mitigation Action |
| :--- | :---: | :---: | :--- |
| Network disruption during top 1,000 crawl | Medium | Medium | SQLite persistence and `--resume` flag enable resuming without lost visits. |
| Time constraint on writing Chapter 7 | Medium | Low | Utilizing structured analytical prompts in `contextual_analysis_prompts.md`. |
| Hand-labelling sample bottleneck | Low | Medium | Stratified sampler generates small, high-leverage 100-script validation template. |

---

## 4-Minute Verbal Update Outline (For the Meeting)

Use this structured speaking outline to brief your supervisor efficiently during the first 4 minutes of your meeting:

1. **Minute 1: High-Level Status & Milestone Progress**
   - *"This week, the core measurement pipeline achieved a major milestone: the automated test suite reached 87.4% coverage and `fpstudy selfcheck` verified that our browser hooks and countermeasure canaries are functioning correctly."*
2. **Minute 2: Key Empirical Findings & Figures**
   - *"I ran paired crawls across our top 1,000 sample. Looking at Figure 1 in the report, canvas and font probing remain the predominant vectors. Our paired McNemar test shows that network blocklists achieved an Absolute Risk Reduction of X% with p < 0.001."*
3. **Minute 3: Writing Progress & Dissertation Deliverables**
   - *"On the dissertation draft, I have completed the first draft of Chapter 3 detailing our detection criteria from Englehardt & Narayanan. I also established the contextual analysis structure for the UK GDPR and PECR discussion in Chapter 7."*
4. **Minute 4: Discussion Topics & Decisions Needed Today**
   - *"Today, I would appreciate your input on two specific questions: first, the presentation format for our breakage analysis table, and second, confirming whether our department requires formal ethics committee notification for public web crawling."*
