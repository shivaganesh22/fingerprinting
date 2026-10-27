# Study Limitations & Technical Caveats (`docs/limitations.md`)

This document critically analyzes the methodological, technical, and ecological limitations of the study. A rigorous understanding of these constraints is vital for an MSc dissertation defense and viva examination.

---

## 1. Script Attribution Constraints

### 1.1 Minification and Bundler Inlining
Modern web development relies heavily on bundlers (Webpack, Vite, Rollup, esbuild) that merge first-party application code and dozens of third-party NPM libraries into monolithic files (e.g., `app.min.js`, `vendor.js`, `chunk-482.js`).
- **Limitation:** When a bundled vendor script calls canvas or WebGL APIs, the stack trace URL points to the monolithic bundle. If the bundle is hosted on the site's own origin, `tldextract` classifies it as **first-party**, obscuring third-party tracking attribution.
- **Impact:** Potential undercounting of third-party script attribution and overcounting of apparent first-party fingerprinting.

### 1.2 Tag Managers (e.g., Google Tag Manager, Tealium)
Tag managers dynamically inject and execute heterogeneous third-party analytics and ad-tech snippets inside `<script>` or `eval()` blocks.
- **Limitation:** Injected scripts may have dynamic stack frames, `blob:`, or `data:` URLs, tracing back only to the tag manager container rather than the underlying tracking vendor.

### 1.3 `eval()` and Dynamically Injected Code
- Code executed via `eval()`, `new Function()`, or dynamic Web Workers generates anonymous or synthetic stack traces (`eval at ...`, `<anonymous>`). While our stack parser extracts the outer enclosing script URL, deeply nested dynamic evaluations introduce ambiguity.

---

## 2. Browser Automation & Environment Artifacts

### 2.1 Headless Mode Detectability
Despite using `--headless=new` and custom viewport configurations:
- **Limitation:** Sophisticated anti-bot platforms (Cloudflare Turnstile, DataDome, Akamai Bot Manager) detect automation artifacts through browser runtime consistency checks, timing discrepancies, and driver hooks.
- **Impact:** Sites employing aggressive bot detection may serve challenge pages or 403 Forbidden responses, preventing the observation of fingerprinting code that would normally execute for human visitors. Encounters are categorized under `blocked_bot_suspected`.

### 2.2 Lack of User Interaction & Shallow Dwell Times
- **Limitation:** The crawler dwells for a fixed period (default: 12.0 seconds) and performs a synthetic scroll. It does not type, click navigation buttons, accept cookie consent dialogs, or move the mouse organically.
- **Impact:**
  - **Delayed Fingerprinting:** Scripts configured to fire after 30–60 seconds, or those hooked to `window.onbeforeunload`, are truncated.
  - **Event-Driven Fingerprinting:** Behavioral biometric scripts that require keystroke dynamics or continuous mouse tracking will not activate.
  - **Consent Banners:** Some websites conditionally delay loading tracking scripts until the user clicks "Accept" on a GDPR cookie banner. The crawler does not interact with CMPs (Consent Management Platforms), which may lower observed prevalence compared to users who routinely click "Accept All".

### 2.3 Single Vantage Point
- **Limitation:** All crawls originate from a single IP address, geographical region, and network autonomous system (AS).
- **Impact:** Content Delivery Networks (CDNs) and advertising exchanges employ geo-targeting and regulatory compliance gating. For example, sites may disable third-party tracking scripts for EU/UK IP addresses to avoid GDPR liability while executing them freely for US IP addresses.

---

## 3. Browser & Engine Representation

### 3.1 Chromium Primary
- **Limitation:** The core experimental pipeline runs on Chromium via Playwright. While Chromium accounts for the vast majority of web traffic (via Chrome, Edge, Brave, Opera, Vivaldi), it does not represent Gecko (Mozilla Firefox) or WebKit (Apple Safari).
- **Impact:** Safari's Intelligent Tracking Prevention (ITP) and Firefox's Enhanced Tracking Protection (ETP) employ native fingerprinting mitigations that differ structurally from Chromium-based defenses.

---

## 4. Rule-Based Classifier Boundaries

### 4.1 False Positives
- Sophisticated HTML5 charting libraries, 3D WebGL visualizations, interactive CAPTCHAs, and legitimate canvas text rendering may occasionally exhibit patterns resembling device probing. While our exclusion rules (`save`, `restore`, event listener detection) substantially filter these, edge cases remain.

### 4.2 False Negatives
- Novel or evasive fingerprinting techniques—such as subtle font probing using CSS `@font-face` cache timing, WebGPU compute shader benchmarking, or battery/sensor API queries—are outside the four core vector heuristics.

---

## 5. Temporal Drift and Experimental Paired Validity

### 5.1 Temporal Drift
- Running crawls across multiple conditions sequentially (e.g. Baseline today, Blocklist tomorrow) introduces natural temporal variation: websites update scripts, CDNs rotate ad partners, and A/B tests shift traffic.
- **Pipeline Mitigation:** To minimize temporal drift, paired comparisons enforce strict matching on successfully loaded sites ($N_{\text{ok}}$ in both conditions), and noise estimation crawls quantify natural baseline-to-baseline drift.

### 5.2 Tranco List Representativeness
- The Tranco list represents top-ranked root domains based on aggregated traffic ranks. Fingerprinting behavior on high-traffic landing pages may differ from deep inner content pages or the long tail of low-traffic websites.
