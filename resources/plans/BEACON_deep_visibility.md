# BEACON Deep Visibility Research
## Every Source That Drives Visibility — And Exactly How to Win Each One

> **Purpose:** A complete, research-backed map of every platform, source, and channel where a client's brand can earn visibility in 2026 — covering traditional search, AI citation, and entity authority. Includes detection logic for BEACON and actionable guidance for clients.

> **Research basis:** Data from Profound (680M citations), SE Ranking (230K prompts), Ahrefs Brand Radar (76.7M AI Overviews), SurferSEO (36M citations), Semrush AI Visibility Index, SparkToro, AIVO, NP Digital, and others. Dated March–April 2026.

---

## The Brutal Reality First

Before the playbook, four facts that should change how you think about this:

**1. AI and SEO have diverged.** Only 38% of Google AI Overview citations now come from top-10 organic results — down from 76% in mid-2025. 80% of LLM citations don't even rank in Google's top 100 for the original query. You can dominate Google and be invisible to AI.

**2. AI citations are more valuable than rankings.** Brands cited inside AI Overviews earn 35% more organic clicks and 91% more paid clicks than non-cited competitors on the same queries. Being the cited answer is now worth more than being #1 in the list.

**3. Consistency is a myth.** There is less than a 1-in-100 chance that ChatGPT will give you the same list of brand recommendations if asked the same question 100 times. AI visibility is probabilistic, not positional. The goal is increasing citation probability, not owning a rank.

**4. Each AI engine cites completely differently.** ChatGPT's #1 cited source is Wikipedia (47.9% of its top-10 share). Perplexity's #1 is Reddit (46.7%). Google AI Overviews leads with Reddit and YouTube. A single-channel strategy fails by design.

---

## The BEACON Visibility Map

Every source below falls into one of four tiers based on how quickly BEACON can detect it and how directly it impacts AI citation and search visibility.

```
TIER 1 — Detectable by BEACON (technical, on-site)
TIER 2 — Verifiable by BEACON (external presence checks)
TIER 3 — Auditable by BEACON (presence gap detection)
TIER 4 — Advisable by BEACON (content/strategy recommendations)
```

---

## TIER 1: On-Site Technical Signals
### Detectable in a single URL scan

---

### 1. AI Crawler Access (robots.txt)

**What it is:** Whether AI company bots are permitted to crawl and index the site.

**Why it's critical:** If blocked, the site is permanently invisible to that AI engine regardless of content quality. This is the #1 most impactful immediate fix.

**Crawlers to check:**

| Bot | Platform | Impact if Blocked |
|---|---|---|
| `GPTBot` | ChatGPT (training + browse) | Invisible to ChatGPT permanently |
| `ChatGPT-User` | ChatGPT live browsing | Not cited in ChatGPT web searches |
| `PerplexityBot` | Perplexity | Not cited in Perplexity answers |
| `Google-Extended` | Google AI training + Gemini | Weakens Gemini visibility |
| `ClaudeBot` | Anthropic / Claude | Not in Claude training data |
| `CCBot` | Common Crawl (feeds many LLMs) | Excluded from LLM training sets |
| `Googlebot` | Google (feeds Gemini via index) | Entire Google ecosystem blocked |
| `bingbot` | Bing (feeds ChatGPT search) | ChatGPT web search can't find it |

**BEACON detection:**
```python
import urllib.robotparser
rp = urllib.robotparser.RobotFileParser()
rp.set_url(f"{base_url}/robots.txt")
rp.read()
blocked = [agent for agent in AI_CRAWLERS if not rp.can_fetch(agent, "/")]
```

**Client fix:** Remove disallow rules for these agents, or if intentional (GDPR), document that decision explicitly.

---

### 2. Structured Data / Schema.org

**What it is:** JSON-LD markup that tells search engines and AI exactly what a page is about, who made it, and what actions are possible.

**Why it's critical:** Pages with structured data are 28% more likely to be cited by Perplexity. FAQPage schema alone increases AI Overview inclusion by 40%. This is the highest-ROI on-page technical change.

**Schema types ranked by AI visibility impact:**

| Schema Type | AI Impact | Google Impact | Pages It Belongs On |
|---|---|---|---|
| `FAQPage` | 🔴 Critical | 🔴 Critical | Landing pages, pricing, product pages |
| `Organization` + `sameAs` | 🔴 Critical | 🔴 Critical | Homepage only |
| `Article` / `BlogPosting` | 🔴 Critical | 🟡 High | All blog/content pages |
| `HowTo` | 🟡 High | 🟡 High | Tutorial/guide pages |
| `WebSite` + `SearchAction` | 🟡 High | 🟡 High | Homepage only |
| `Product` + `Offer` | 🟡 High | 🔴 Critical (e-commerce) | Product pages |
| `BreadcrumbList` | 🟢 Medium | 🟡 High | All pages |
| `Person` (authors) | 🟡 High | 🟡 High | Author pages, about page |
| `LocalBusiness` | 🔴 Critical (local) | 🔴 Critical (local) | Local businesses only |
| `Review` / `AggregateRating` | 🟡 High | 🟡 High | Product/service pages |
| `ItemList` | 🟡 High | 🟡 High | Category/comparison pages |
| `SpeakableSpecification` | 🟡 High (voice) | 🟢 Medium | Key answer sections |

**The `sameAs` property is the entity linker.** In `Organization` schema, `sameAs` should link to:
- Wikipedia URL (if exists)
- Wikidata URL (Q-number URL)
- LinkedIn company page
- Twitter/X profile
- Crunchbase profile
- Google Business Profile

This creates the "closed loop of identity" — AI systems verify the entity by cross-referencing these linked sources.

**BEACON detection:** Use `extruct` for extraction, then check presence/completeness of each type against page type inference.

---

### 3. Content Structure for AI Extraction

**What it is:** How content is formatted so AI engines can extract and cite specific passages.

**Key finding:** 44.2% of all LLM citations pull from the first 30% of content. Only 24.7% come from the final third. **Front-load everything important.**

**Signals BEACON can detect:**

| Signal | Detection Method | AI Impact |
|---|---|---|
| Question-format H2/H3 headings | Regex: heading starts with "How", "What", "Why", "When" | High — AI uses as query match |
| Answer capsule after question heading | Check if first paragraph after question-H2 is ≤70 words | Critical — direct extraction target |
| Listicle/comparison structure | `<ul>/<ol>` density + comparison table detection | High — 25.37% of all AI citations are lists |
| Statistics with source attribution | Regex: number + "%" or number + unit + link | High — 30-40% more citations with attributed data |
| Definition blocks | Short bolded or first-paragraph definitions | High — AI Overview "define X" triggers |
| `datePublished` / `dateModified` | Article schema fields | High — AI prefers fresh content |
| Author byline with credentials | `Person` schema + visible byline | High — E-E-A-T signal |
| Table data | `<table>` elements with headers | High — AI extracts comparison tables directly |

**Pages with FCP under 0.4 seconds average 6.7 AI citations. Pages with FCP over 1.13 seconds average only 2.1.** Speed is a direct AI citation multiplier, not just a UX concern.

---

### 4. `llms.txt` Standard

**What it is:** A markdown file at `{domain}/llms.txt` that explicitly tells AI systems what to read, similar to `robots.txt` but designed for LLMs.

**BEACON detection:** `httpx HEAD {domain}/llms.txt` — returns 200 or 404.

**Client recommendation if absent:** Create it. A basic `llms.txt` takes 30 minutes and signals to compatible AI systems exactly which pages represent the site's authoritative content.

---

## TIER 2: External Presence — Verifiable via API/HEAD Request

These are off-site sources BEACON can check for existence and flag as present/missing.

---

### 5. Google Business Profile (GBP)

**What it is:** Google's free business listing — the foundation of local search and a direct input to the Knowledge Graph.

**AI impact:** Google pulls from GBP to populate Knowledge Panels. Gemini uses Knowledge Panel data when answering brand-specific queries. An unclaimed or incomplete GBP means Google can't verify the business as a real entity.

**BEACON detection:** Search Google's Places API for the business name + location. Flag missing or unverified profiles.

**What a complete GBP needs:**
- Verified ownership (Google postcard or phone)
- All business categories filled (primary + secondary)
- Hours, address, phone consistent with website (NAP consistency)
- Photos (minimum: logo, cover, interior, exterior)
- Products/services listed
- Responding to reviews (Google factors response rate into ranking)
- Posts active (weekly posts improve local pack ranking)

**NAP consistency is critical.** The Name, Address, Phone number on GBP must exactly match what's on the website, in every citation, in every directory. Inconsistency confuses the Knowledge Graph and suppresses entity recognition.

---

### 6. Wikidata Entry

**What it is:** The machine-readable database that powers Google's Knowledge Graph and feeds factual grounding to ChatGPT, Siri, Alexa, Bing, and virtually every AI system.

**Why it's the most underrated visibility lever:** Unlike Wikipedia (which requires notability), any real business can create a Wikidata entry. It is the single most direct way to tell AI systems "this entity exists, here is what it is."

**AI impact:**
- Powers Knowledge Panels on Google
- ChatGPT uses Wikidata for factual grounding
- Enables the `sameAs` entity linkage in Organization schema
- "Collapses identity ambiguity" — when multiple sources reference the same Wikidata Q-number, AI stops guessing and starts citing

**What a Wikidata entry needs:**
- Instance of (`P31`): organization, company, software, etc.
- Official website (`P856`): canonical URL
- Country (`P17`): operating country
- Industry (`P452`): industry classification
- Founded (`P571`): founding date
- Founder (`P112`): links to founder's Wikidata entry
- Logo image (`P154`): via Wikimedia Commons
- LinkedIn (`P4264`): company page URL
- Crunchbase (`P2088`): company ID
- Description: short 1-sentence description in multiple languages

**BEACON detection:** Query `https://www.wikidata.org/w/api.php?action=wbsearchentities&search={company_name}` — returns existing entries or empty.

**Timeline:** 3–6 months of consistent entity signal building (Schema + Wikidata + PR) typically triggers a Knowledge Panel.

---

### 7. Wikipedia Presence

**What it is:** A Wikipedia article about the brand, person, or product.

**AI impact:** Wikipedia is ChatGPT's single most cited source at 7.8% of total citations (47.9% of its top-10 share). Having a Wikipedia article is the highest-authority citation signal that exists for any AI engine.

**The problem:** Wikipedia requires "notability" — demonstrable coverage in reliable secondary sources. Not every business qualifies. But BEACON can check if a page exists and flag it as a high-value opportunity if the client has the PR coverage to qualify.

**BEACON detection:** `httpx HEAD https://en.wikipedia.org/wiki/{brand_name}` — 200 or 404.

**If absent and client qualifies:** Recommend Wikipedia article creation as a high-priority initiative. Requirements are: coverage in multiple independent reliable sources, not just press releases or company-controlled content.

---

## TIER 3: Third-Party Platform Presence
### Presence gaps BEACON detects, client fills

This is where most businesses have the biggest untapped opportunity. The research is unambiguous: third-party platform presence multiplies AI citation rates far beyond what website optimization alone can achieve.

---

### 8. Review Platforms (B2B / SaaS)

**The data:** Domains with profiles on G2, Capterra, and Trustpilot have **3x higher chances of being cited by ChatGPT** than sites without them. These platforms are structurally trusted by AI — they have verification systems, editorial standards, and high domain authority.

**Platform breakdown:**

| Platform | AI Relevance | Best For | Citation Notes |
|---|---|---|---|
| **G2** | 🔴 #1 B2B software source across all AI platforms | SaaS, B2B software | 33% of software review citations in ChatGPT; 75% in Perplexity |
| **Capterra** | 🔴 High (now G2-owned) | SMB software | Strong Google AI Overviews presence |
| **Trustpilot** | 🔴 #5 most cited domain globally on ChatGPT | All business types | 15x growth in AI-driven click-throughs YoY |
| **Product Hunt** | 🟡 Medium | Consumer/developer tools | Feeds tech-focused AI answers |
| **Clutch** | 🟡 Medium | Agencies, services | B2B service queries |
| **Google Reviews** | 🔴 Critical (local) | All local businesses | Direct GBP input |
| **Yelp** | 🟡 Medium | Local/consumer | Perplexity local queries (0.8% of citations) |

**What to optimize per platform:**
- Complete all profile fields (missing fields = lower authority score in AI)
- Minimum 10 reviews (below this threshold, AI treats profile as low-authority)
- Recent reviews matter — AI engines weight recency heavily
- Respond to every review (shows active entity management)
- Consistent NAP: name, address, phone must match website exactly
- Category selection: choose the most specific available category
- Feature/comparison data: on G2, fill out every comparison field — AI extracts comparison tables directly

---

### 9. Reddit Presence

**The data:** Reddit accounts for **46.7% of Perplexity's top-10 citation share** and **21% of Google AI Overviews citations**. It is the single most cited source across all AI platforms when measured by citation volume.

**Why AI loves Reddit:** Authentic, experience-based content provides "Information Gain" — unique insights that brand-produced content cannot replicate. AI engines explicitly value UGC over vendor marketing.

**The right approach (not the wrong one):**

❌ **Wrong:** Create branded accounts, promotional posts, astroturfing  
✅ **Right:** Identify 3–5 subreddits where target customers discuss problems. Provide genuinely helpful answers. Mention the product only when directly relevant and disclosed. Build karma over months, not days.

**How to find the right subreddits:**
- Search Reddit for the client's main use case ("site audit", "web accessibility", "SEO tools")
- Look for subreddits with 10K–500K members (large enough to be indexed, small enough to be findable)
- Check which subreddits appear in Google/Perplexity results for target queries
- Typical targets: r/SEO, r/webdev, r/webdevelopment, r/entrepreneur, r/startups, r/digitalmarketing

**Content that gets AI-cited from Reddit:**
- Detailed how-to comments (step-by-step with specifics)
- Comparison threads ("I tested X vs Y, here's what I found")
- Problem-solving responses with actual data or screenshots
- Threads that answer "what's the best X for Y" questions

**Timeline:** Reddit authority builds over months. New accounts get less traction. The goal is genuine participation, not quick wins.

---

### 10. Quora Presence

**The data:** Quora appears prominently in Google AI Overviews and traditional results. 40% of Quora's desktop traffic comes from Google. A well-crafted Quora answer on the right question can generate compounding traffic for years.

**AI citation preference:** Quora rewards structured, expert-level responses. Unlike Reddit's conversational style, Quora answers that demonstrate clear expertise on niche professional questions get cited by Gemini and Google AI Overviews regularly.

**What works on Quora:**
- Answer questions your target customers are asking (not questions about your product)
- Lead with the definitive answer in the first sentence
- Include specific data, numbers, and methodology
- Add credentials in your profile bio (they're displayed with every answer)
- Target questions with 1K–50K monthly views (detectable via Quora stats)

---

### 11. LinkedIn Presence

**The data:** LinkedIn is the **most-cited domain for professional queries** across AI Overviews, AI Mode, ChatGPT, Microsoft Copilot, and Perplexity (Profound, March 2026). For B2B businesses, LinkedIn visibility directly feeds AI citation probability.

**What matters for AI visibility:**

*Company page:*
- Complete all fields (industry, company size, description, website, logo)
- Regular posts (minimum 2x/week)
- Employee count and employee profiles linked to company page
- Products/services section filled
- Consistent messaging with website and other platforms

*Executive profiles:*
- Named founders/executives with complete profiles = E-E-A-T signal
- "About" section with expertise and credentials
- Regular thought leadership posts
- Articles (LinkedIn articles get indexed and cited separately from posts)

*Content that gets cited:*
- Original data or research
- Industry comparisons and analyses
- How-to content with specific steps
- Opinion pieces from named executives

---

### 12. YouTube Presence

**The data:** YouTube is cited in **16.1% of Perplexity responses** and **9.5% of Google AI Overviews** — second only to Wikipedia/Reddit on many platforms. SurferSEO's analysis found YouTube accounts for ~23.3% of citations across industries.

**AI citation triggers from YouTube:**
- Video transcripts (AI extracts text from transcripts)
- Video descriptions (must be comprehensive, structured)
- Video titles that match query intent exactly
- Channel authority (subscriber count affects citation probability)

**What to produce for AI visibility:**
- Tutorial/how-to videos (highest citation rate by content type)
- Comparison videos ("X vs Y: which is better for [use case]")
- Case study walkthroughs with specific metrics
- Explainer videos for the client's category

**Technical requirements:**
- Auto-generated or manual transcripts must be enabled
- Chapters (timestamps) improve content extractability
- Full descriptions (500+ words) with structured information
- Category tags must be specific and accurate

---

### 13. Medium and Cross-Publishing Platforms

**The data:** Medium ranks high in Perplexity citations for technical topics. NP Digital's analysis found niche blogs and independent publishers appear more often in Perplexity than in Gemini or ChatGPT — Perplexity levels the playing field for smaller publishers.

**The strategy:** Cross-publish in-depth technical content on Medium, Substack, or Dev.to. These platforms have accumulated domain authority that new company blogs don't have yet. The same content on Medium may get cited by Perplexity before the original company blog does.

**Content types that work:**
- Deep technical tutorials
- Original research and data
- Opinionated takes backed by evidence
- Case studies with specific numbers

---

### 14. Industry-Specific Directories and Databases

**What it is:** Every industry has authoritative directories that AI engines treat as trust signals. Being listed — with complete, accurate information — is a direct AI citation lever.

**Universal directories (every business):**

| Directory | Domain Authority | AI Impact | Free? |
|---|---|---|---|
| Crunchbase | Very high | ChatGPT entity verification | Free basic |
| Bloomberg Business | Very high | Finance/enterprise queries | Requires coverage |
| LinkedIn Company | Very high | Professional queries | Free |
| Google Business Profile | Critical | All Google AI products | Free |
| Apple Maps / Yelp | High | Local/voice queries | Free |
| Better Business Bureau | Medium | Trust queries | Free |

**Tech/SaaS specific:**

| Directory | AI Impact | Why |
|---|---|---|
| G2 | 🔴 Critical | Most cited B2B software source |
| Capterra | 🔴 Critical | G2-owned, massive citation share |
| Product Hunt | 🟡 High | Tech-focused AI answers |
| AngelList / Wellfound | 🟡 High | Startup entity verification |
| BuiltWith | 🟢 Medium | Technology stack authority |
| AlternativeTo | 🟡 High | Comparison query citations |
| Slant | 🟢 Medium | "Best alternative to X" queries |

**Agency/services specific:**
- Clutch (services firms)
- UpCity (marketing agencies)
- Sortlist (agencies)
- Expertise.com (local services)

**What all directory listings need:**
- NAP consistency: Name, Address, Phone identical across all platforms
- Identical business category across platforms
- Same short description (vary slightly to avoid duplicate content flags)
- Link back to website (canonical URL, not a redirect)

---

### 15. Press and Media Coverage

**The data:** AP News, Yahoo Finance, MarketWatch, and Benzinga sit inside the citation ecosystem AI engines trust. Press release citations in AI tools grew 5x between July and December 2025.

**However:** Press releases on wire services alone account for just 0.04% of AI citations. Syndicated placement matters enormously — it's not about sending a release, it's about where it lands.

**The citation hierarchy for press:**

| Outlet/Channel | Citation Probability | Notes |
|---|---|---|
| AP News | 🔴 Very high | Core media ecosystem, all AI platforms trust |
| Reuters | 🔴 Very high | Especially strong in ChatGPT |
| Yahoo Finance `/news/` path | 🔴 High | Confirmed citations in ChatGPT and Gemini |
| MarketWatch | 🟡 High | Finance queries, Google AI and Perplexity |
| TechCrunch, Wired, The Verge | 🔴 High | Tech queries, all platforms |
| Forbes, Inc., Fast Company | 🔴 High | Business/brand queries |
| Raw PRNewswire.com URL | 🟡 Medium (Perplexity only) | ChatGPT and Gemini often skip raw wire |
| Local news outlets | 🟢 Medium | Local SEO and entity verification |

**What drives editorial coverage (not press releases):**
- Original research and proprietary data (strongest trigger)
- Contrarian or surprising findings
- Industry surveys with unique results
- Notable customer wins or case studies
- Executive thought leadership with a clear POV

---

## TIER 4: Strategic Content Recommendations
### What BEACON advises, client executes

These cannot be fully automated but BEACON can detect the gaps and provide specific guidance.

---

### 16. Answer-Ready Content Architecture

**What it is:** Restructuring existing pages so AI engines can extract clean, citable answers without effort.

**The 44.2% rule:** Almost half of all AI citations come from the first 30% of content. Every important claim, definition, and answer must appear before the fold of the article.

**The Answer Capsule pattern:**

```markdown
## How does [X] work?

[Product/topic] works by [direct answer in 40-60 words, 
using specific language]. [One supporting sentence with data.]

### Detailed Explanation
[Extended content follows...]
```

This pattern directly mirrors how Perplexity and Google AI Overviews extract answers. The question-format heading matches user queries. The short answer paragraph is the extractable snippet. The extended content provides authority signals.

**Content types by AI citation rate:**
1. Listicles and comparisons (25.37% of all AI citations)
2. Articles with answer capsules (40% higher citation rate)
3. How-to guides with numbered steps
4. FAQ pages with FAQPage schema
5. Definition pages ("What is X")
6. Original research with attributed statistics

---

### 17. Entity Consistency Audit

**What it is:** Ensuring the brand's name, description, category, and key facts are consistent across every platform where it exists.

**Why AI cares:** AI engines cross-reference multiple sources to verify entity claims. Inconsistencies reduce confidence that sources are referring to the same entity. Consistent entities get cited; ambiguous ones don't.

**The "closed loop of identity" strategy:**
1. Define canonical facts: exact legal name, one-sentence description, founding year, headquarters, primary category
2. Apply these facts identically to: website, GBP, Wikidata, LinkedIn, Crunchbase, G2, all directories
3. Add `sameAs` links in Organization schema pointing to each platform
4. Monitor for drift (any platform showing different information)

**BEACON's role:** Detect `Organization` schema on the website. Check if `sameAs` fields are present and populated. Flag missing external links. Score entity consistency.

---

### 18. E-E-A-T Signal Building

**What it is:** Google's quality framework (Experience, Expertise, Authoritativeness, Trustworthiness) has become the primary quality filter for AI citation decisions across all platforms.

**The branded mentions finding (critical):** Ahrefs' analysis of 75,000 brands found that branded web mentions had the strongest correlation with AI Overview visibility (Spearman r = 0.664) — higher than backlinks (0.587) or domain rating (0.572). **Brand mentions are now more predictive of AI visibility than backlinks.**

**E-E-A-T signals BEACON can detect:**
- Named author with credentials in article schema
- `Person` schema for key executives on about page
- Contact page present
- Privacy policy present
- About page with team bios
- External citations/links from the content

**E-E-A-T signals BEACON recommends (not detectable):**
- Publish original research (even small-scale surveys count)
- Get named in industry publications (Forbes, TechCrunch, industry blogs)
- Speak at conferences (mention on conference sites = citation)
- Academic or professional credentials visible for authors
- Case studies with verifiable client names and metrics

---

## The Platform-by-Platform Strategy

### To win in ChatGPT Search:

1. Ensure `bingbot` is not blocked (ChatGPT uses Bing's index for web search)
2. Submit sitemap to **Bing Webmaster Tools** (not just Google — this is the first step)
3. Get listed on Wikipedia, G2, and Trustpilot (top cited domains in ChatGPT)
4. Build Wikidata entry (ChatGPT uses Wikidata for factual grounding)
5. Create structured, definition-style content (ChatGPT prefers encyclopedic format)
6. Ensure `GPTBot` is not blocked

### To win in Perplexity:

1. Ensure `PerplexityBot` is not blocked
2. Build genuine Reddit presence in relevant subreddits (46.7% of Perplexity's top citations)
3. Publish on Medium or similar high-DA platforms
4. Use structured headers and answer capsules throughout content
5. Include cited statistics (numbers with source attribution)
6. Keep content fresh — Perplexity explicitly penalizes outdated content
7. Get listed on G2 (75% of software review citations in Perplexity come from G2)

### To win in Google AI Overviews / Gemini:

1. Traditional SEO is the prerequisite (76.1% of AI Overview citations also rank in Google's top 10 — *though this dropped from 76% to 38% in just 6 months, so don't rely on this*)
2. Implement `FAQPage` schema on every key landing page
3. Ensure `Google-Extended` is not blocked
4. Build Reddit and YouTube presence (top cited in AI Overviews)
5. E-E-A-T signals — Google's quality systems feed directly into Gemini
6. `HowTo` schema on tutorial content
7. Verify Google Business Profile if local business

### To win in Voice / Google Assistant:

1. `SpeakableSpecification` schema on key answer sections
2. `LocalBusiness` schema for local businesses
3. `FAQPage` schema (voice assistants read FAQ answers directly)
4. Short, direct answers in the first paragraph of every page
5. Clean, complete GBP (voice queries primarily pull from Knowledge Graph)

---

## The BEACON Product Opportunity Map

This research reveals a product expansion opportunity beyond technical auditing:

**What BEACON detects today (Tier 1):**
Website technical signals, structured data, content structure, AI crawler access

**What BEACON could surface tomorrow (Tiers 2–3):**
Presence gaps across external platforms, NAP consistency failures, entity verification status

**What BEACON could automate eventually (Tier 4):**
Generating the exact Organization schema with all `sameAs` fields populated, generating `llms.txt`, generating FAQPage schema from existing content, generating structured meta content

**The agency upsell opportunity:**
BEACON's audit reveals the gap. The agency gets paid to fill it. A full "AI Visibility Sprint" for a client could include:
1. BEACON technical audit ($0 — trial/lead gen)
2. Wikidata entry creation (2 hours work, high value)
3. G2/Capterra/Trustpilot profile setup and review generation campaign
4. Reddit presence strategy and 30-day execution
5. Content restructuring for answer capsules
6. Schema implementation from BEACON's generated fixes

This is a $2,000–$10,000 one-time engagement per client — and agencies can charge it because BEACON gives them the evidence justifying every line item.

---

## Key Statistics for BEACON's UI / Sales Materials

| Stat | Source | Use In |
|---|---|---|
| Brands with G2/Trustpilot profiles: **3x more ChatGPT citations** | SE Ranking, Nov 2025 | Agency pitch |
| Reddit/Quora presence: **4x higher citation rates** | SE Ranking, Nov 2025 | Agency pitch |
| AI citations earn **35% more organic + 91% more paid clicks** | Seer Interactive via AIVO | Client ROI |
| 44.2% of LLM citations from **first 30% of content** | Growth Memo, Feb 2026 | Content advice |
| FAQPage schema: **40% higher citation rate** | Backlinko GEO research | Schema pitch |
| Branded mentions: **r=0.664 correlation** with AI visibility (higher than backlinks) | Ahrefs, 75K brands | Authority pitch |
| Only **38% of AI Overview citations** from top-10 Google results (down from 76%) | Ahrefs, March 2026 | Why GEO matters |
| AI-referred traffic grew **527% in H1 2025** | Multiple sources | Market timing |
| Pages loading < 0.4s: **6.7 avg citations**; >1.13s: **2.1 citations** | Multiple sources | Speed = AI signal |
| **<1 in 100 chance** ChatGPT gives same brand list twice | SparkToro, Jan 2026 | Why breadth matters |

---

## What BEACON Cannot Solve (And Must Be Honest About)

Transparency here is a product moat, not a weakness. Clients trust tools that are honest about limits.

| Gap | Why BEACON Can't Solve It | What Client Needs |
|---|---|---|
| Backlink building | Requires outreach, content, relationships | SEO agency |
| Wikipedia notability | Requires independent press coverage | PR campaign |
| Reddit karma and community trust | Takes months of authentic participation | Content team |
| Google Search Console data | Requires OAuth per domain | Client setup |
| AI citation monitoring | Requires querying ChatGPT/Perplexity live | AIVO, Profound, or Semrush |
| Training data inclusion | Fundamentally unknowable | No tool can solve this |
| Content quality depth | Requires human expertise | Writers, subject matter experts |

**The honest framing for clients:** "BEACON fixes the technical floor — everything that's in your control on your website and external profiles. The ceiling is determined by your content quality and brand authority, which require ongoing investment. We show you exactly what's broken; we can't write your articles or earn your press coverage."

---

*BEACON Deep Visibility Research — April 2026*
*Internal reference. Cited sources: Profound, SE Ranking, Ahrefs, SurferSEO, Semrush, AIVO, SparkToro, NP Digital, Backlinko, Growth Memo, BrightEdge.*
