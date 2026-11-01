# Ethics and Responsible Crawling Policy (`docs/ethics.md`)

This document outlines the ethical principles, politeness constraints, and data handling protocols governing the `fpstudy` measurement pipeline.

---

## 1. Automated Web Measurement Ethics

Measuring third-party web services involves interacting with servers owned by diverse organizations worldwide. Our methodology adheres to established Internet measurement research norms (e.g., Dittrich & Kenneally, *The Menlo Report: Ethical Principles Guiding Information and Communication Technology Research*, 2012).

### 1.1 Politeness & Rate Limiting
- **Per-Domain Delays:** The crawler strictly enforces a minimum inter-request delay (default: 5.0 seconds) for any given origin. Subsequent requests to the same origin are queued and throttled.
- **Global Concurrency Cap:** Concurrency is bounded (default: 4 concurrent browser contexts) to ensure the host system does not create localized network congestion or flood server infrastructures.
- **Non-Aggressive Dwell Times:** Pages are loaded and observed passively for a bounded dwell time (default: 12.0 seconds), avoiding rapid reloading or continuous connection thrashing.

### 1.2 Robots Exclusion Protocol (robots.txt)
- Before initiating navigation to any domain, the crawler requests and parses the origin's `robots.txt` file (cached per origin in memory).
- If the configured User-Agent is explicitly disallowed from accessing the root path (`/`), the crawler immediately skips navigation and records `status = 'skipped_robots'`.
- If a `Crawl-Delay` directive is specified in `robots.txt`, the pipeline dynamically increases the per-domain delay to respect the webmaster's explicit instruction.

### 1.3 Identification & Transparency
- The crawler configures a distinctive User-Agent header incorporating the project version and an institutional contact email:
  ```text
  Mozilla/5.0 ... fpstudy-research/1.0 (+mailto:researcher@institution.ac.uk)
  ```
- **Failsafe Verification:** The pipeline verifies that the research contact email has been explicitly configured in `config/default.yaml`. If the default placeholder (`CONTACT_FROM_CONFIG`) is detected, the crawler refuses to execute.

---

## 2. Safety, Non-Interference & Legal Boundaries

### 2.1 Strictly Passive Observation
- **No Form Submissions:** The crawler never inputs data into web forms, registration fields, search boxes, or comment sections.
- **No Authentication:** The crawler operates entirely without user accounts, cookies, or credentials. It never accesses password-protected or authenticated areas.
- **No Paywall or Access-Control Bypass:** If a website presents a paywall, age gate, or access restriction, the crawler does not attempt to circumvent it.
- **No Anti-Bot Evasion:** The crawler does not attempt to solve CAPTCHAs, spoof IP addresses via residential proxies, or bypass bot detection shields (e.g., Cloudflare, DataDome, PerimeterX). Encounters with bot challenge screens are logged neutrally under the failure taxonomy as `blocked_bot_suspected`.

---

## 3. Data Protection and Minimization (UK GDPR & DPA 2018)

Under the UK General Data Protection Regulation (UK GDPR) and Data Protection Act 2018, processing must adhere to the principle of **data minimization** (Article 5(1)(c)):

1. **No Personal Data Stored:**
   - The crawler does not collect, record, or store user accounts, cookies, browsing histories, IP addresses of other users, or user-generated communications.
2. **Minimal Necessary Storage:**
   - The SQLite storage engine stores only:
     - Target domain and initial/final URLs.
     - HTTP status codes, navigation timings, and error taxonomy labels.
     - Client-side JavaScript API call traces (method name, aggregated argument dimensions, and script URLs).
3. **No Page Content Archival:**
   - Full HTML DOM dumps, page screenshots, video recordings, and downloaded media assets are intentionally excluded from storage.

---

## 4. Institutional Ethics & IRB Review Prompt

> [!IMPORTANT]
> **Action Required for Dissertation Students:**
> Institutional Research Ethics Review policies vary across universities. While internet measurement research analyzing public websites without human participants often falls under low-risk or exempt categories, **you must verify your university's specific ethical review requirements.**
>
> **Do not assume approval is or is not required.**
>
> 1. Consult your institution's Academic Ethics Committee or Institutional Review Board (IRB) guidelines for Internet-mediated research.
> 2. Submit an ethics self-assessment or checklist to your project supervisor prior to executing large-scale crawls.
> 3. Document your university's ethical decision, protocol reference number (if applicable), or formal exemption status directly in Chapter 3 (Methodology) and Chapter 7 (Contextual & Ethical Analysis) of your dissertation.
