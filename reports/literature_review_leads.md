# Literature Review Leads (`reports/literature_review_leads.md`)

This document provides a curated list of candidate academic papers, conference publications, and technical reports relevant to browser fingerprinting, detection mechanisms, privacy defenses, and data protection law.

> [!CAUTION]
> **Academic Integrity Notice for Dissertation Writing:**
> Each reference below is marked **UNVERIFIED: check the citation yourself**.
> You must manually retrieve the authoritative publication, verify author lists, conference/journal venues, page numbers, publication years, and DOIs before citing them in your dissertation. **Never copy citations without verifying the primary source.**

---

## 1. Seminal Fingerprinting Measurement & Vector Studies

### Mowery & Shacham (2012)
- **Candidate Title:** *Pixel Perfect: Fingerprinting Canvas in HTML5*
- **Candidate Authors:** Keaton Mowery, Hovav Shacham
- **Candidate Venue:** W2SP (Web 2.0 Security and Privacy Workshop), IEEE
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Introduced the theoretical and empirical foundation of 2D canvas text rasterization entropy arising from graphics hardware, font smoothing, and driver variations.

### Acar et al. (2013)
- **Candidate Title:** *FPDetective: Dusting the Web for Fingerprinters*
- **Candidate Authors:** Gunes Acar, Marc Juarez, Nick Nikiforakis, Claudia Diaz, Seda Gürses, Frank Piessens, Bart Preneel
- **Candidate Venue:** ACM Conference on Computer and Communications Security (CCS 2013)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** First large-scale measurement study of font probing (Flash and JS) and screen characteristics across popular domains.

### Acar et al. (2014)
- **Candidate Title:** *The Web Never Forgets: Persistent Tracking Mechanisms in the Wild*
- **Candidate Authors:** Gunes Acar, Christian Eubank, Steven Englehardt, Marc Juarez, Arvind Narayanan, Claudia Diaz
- **Candidate Venue:** ACM Conference on Computer and Communications Security (CCS 2014)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Major study documenting canvas fingerprinting deployed in the wild (including AddThis), canvas font probing, and cookie respawning.

### Fifield & Egelman (2015)
- **Candidate Title:** *Fingerprinting Web Users Through Font Metrics*
- **Candidate Authors:** David Fifield, Serge Egelman
- **Candidate Venue:** Financial Cryptography and Data Security (FC 2015)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Formalized the methodology for measuring installed font differences via DOM element layout bounding boxes (`offsetWidth/offsetHeight`) against generic fallbacks.

### Englehardt & Narayanan (2016)
- **Candidate Title:** *Online Tracking: A 1-million-site Measurement and Analysis*
- **Candidate Authors:** Steven Englehardt, Arvind Narayanan
- **Candidate Venue:** ACM Conference on Computer and Communications Security (CCS 2016)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** The landmark OpenWPM measurement paper. Defined the precise heuristic rules for Canvas, WebGL, AudioContext, and WebRTC tracking that form the basis of our detection heuristics.

### Cao et al. (2017)
- **Candidate Title:** *(Cross-)Browser Fingerprinting via OS and Hardware Level Features*
- **Candidate Authors:** Yinzhi Cao, Song Li, Erik Wijmans
- **Candidate Venue:** Network and Distributed System Security Symposium (NDSS 2017)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Investigated cross-browser fingerprinting using WebGL compute tasks, audio synthesis frequency responses, and camera/microphone device enumerations.

---

## 2. Comprehensive Surveys & System Studies

### Laperdrix et al. (2020)
- **Candidate Title:** *Browser Fingerprinting: A Survey*
- **Candidate Authors:** Pierre Laperdrix, Nataliia Bielova, Benoit Baudry, Gildas Avoine
- **Candidate Venue:** ACM Transactions on the Web (TWEB), Vol. 14, No. 2
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Authoritative survey covering the entire taxonomy of fingerprinting vectors, browser defense mechanisms, entropy metrics, and legal implications.

### Iqbal et al. (2021)
- **Candidate Title:** *FP-Inspector: A Tool for Detecting Browser Fingerprinting Activities*
- **Candidate Authors:** Umar Iqbal, Steven Englehardt, Zubair Shafiq
- **Candidate Venue:** IEEE Symposium on Security and Privacy (S&P 2021)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Explores combining dynamic API tracing with machine-learning classifiers to detect evasion techniques and script attribution. Useful comparison point against our transparent rule-based classifier.

### Vastel et al. (2018)
- **Candidate Title:** *FP-STALKER: Tracking Browser Fingerprint Evolutions*
- **Candidate Authors:** Antoine Vastel, Pierre Laperdrix, Walter Rudametkin, Romain Rouvoy
- **Candidate Venue:** IEEE Symposium on Security and Privacy (S&P 2018)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Investigates temporal drift and how browser fingerprints naturally change over days and weeks due to software updates and font additions. Essential for justifying our paired baseline-to-baseline noise estimation.

---

## 3. Web Measurement Methodology & Web Rankings

### Le Pochat et al. (2019)
- **Candidate Title:** *Tranco: A Research-Oriented Top Sites Ranking Hardened Against Manipulation*
- **Candidate Authors:** Victor Le Pochat, Tom Van Goethem, Samaneh Tajalizadehkhoob, Maciej Korczyński, Wouter Joosen
- **Candidate Venue:** Network and Distributed System Security Symposium (NDSS 2019)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Justification for using Tranco over Alexa, Cisco Umbrella, or Chrome UX Report; addresses churn and manipulation resistance in internet measurements.

---

## 4. Privacy Countermeasures & Defensive Technologies

### Snyder et al. (2021)
- **Candidate Title:** *SugarCoat: Programmatically Generating Privacy-Preserving Alternative Scripts*
- **Candidate Authors:** Peter Snyder, et al.
- **Candidate Venue:** ACM CCS or Privacy Enhancing Technologies Symposium (PETS)
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Explores mocking/stubbing tracking APIs instead of outright request blocking to prevent page breakage.

### Laperdrix et al. (2015)
- **Candidate Title:** *Beauty and the Beast: Diverting modern web browsers to build unique browser fingerprints*
- **Candidate Authors:** Pierre Laperdrix, Walter Rudametkin, Benoit Baudry
- **Candidate Venue:** IEEE Symposium on Security and Privacy (S&P 2016) / AmIUnique dataset
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Demonstrates the paradox of privacy extensions: extensions that inject noise or spoof headers often make users stand out as more unique rather than less unique.

---

## 5. Regulatory, Legal & Data Protection Foundations

### Information Commissioner's Office (ICO, UK)
- **Candidate Resource:** *Guidance on the use of cookies and similar technologies* (Regulation 6 of PECR)
- **Candidate Issuing Body:** UK Information Commissioner's Office
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Clarifies that device fingerprinting involves accessing or storing information on terminal equipment, requiring consent under Regulation 6 of PECR regardless of whether HTTP cookies are used.

### Article 29 Working Party / European Data Protection Board (EDPB)
- **Candidate Resource:** *Opinion 9/2014 on the Device Fingerprinting* (WP 224)
- **Candidate Issuing Body:** Article 29 Data Protection Working Party
- **Status:** **UNVERIFIED: check the citation yourself**
- **Relevance:** Landmark regulatory opinion confirming that device fingerprinting falls squarely within Article 5(3) of the ePrivacy Directive (Directive 2002/58/EC as amended by 2009/136/EC).
