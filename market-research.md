# Body Measurement Tool — Market Research
**Date:** 2026-04-02  
**Status:** Preliminary framework — numbers need verification before any business decision

---

## The Opportunity in One Sentence

Sizing is e-commerce's biggest return problem, custom clothing is growing, and no one has built an accurate, affordable, mobile-first measurement tool for the people who actually make custom clothes.

---

## Market Context

### Custom Clothing
- Global custom/made-to-measure clothing market estimated at $50B+ — **verify, likely stale**
- Growing driven by: sustainability (buy less, buy better), post-COVID fit awareness, influencer-driven personal style
- Still largely manual — most tailors operate with tape measures, paper records, no digital workflow

### E-Commerce Sizing Problem
- Sizing is cited as the #1 driver of apparel returns
- Return rates in online fashion estimated at 20–40% depending on category — **verify**
- Brands lose billions annually to return logistics — strong economic incentive to pay for a fix
- Current solutions (size charts, fit quizzes) are inadequate — brands know this

---

## Competitive Landscape

### Existing Tools

| Company | Approach | Target | Weakness |
|---|---|---|---|
| 3DLOOK | Front + side photo, parametric model | B2B (brands) | Expensive, B2B only, accuracy unverified publicly |
| Bodygram | Mobile photos, ML | B2B (brands, retailers) | Same tier as 3DLOOK |
| MTailor | Video scan | B2C (custom shirts) | Narrow product focus, single brand |
| Sizer.io | Photo-based | B2B retail | Retail-focused, not tailor-grade |
| Smart mirrors / in-store scanners | Hardware | Enterprise retail | High cost, fixed location |

**Pattern:** Every serious player is either B2B-only or locked to their own clothing line. No one is serving the independent tailor market.

### The Gap
No affordable, accurate, mobile tool exists for:
- Independent tailors
- Small custom clothiers
- Alterations shops
- Personal stylists doing custom sourcing

These people currently measure by hand, store in notebooks or spreadsheets, and have no digital client profile.

---

## The Wedge: Independent Tailors & Small Clothiers

### Why this segment first

1. **Underserved** — no tool is built for them. They're not the target of any funded competitor.
2. **Willing to pay** — they charge $200–$2000+ per garment. A tool that saves 15 minutes per client and reduces remakes has obvious ROI.
3. **Data flywheel** — every client measurement taken through your tool is labeled ground truth. This is the asset that makes the model better over time. Tailors *give you this for free* as a byproduct of normal use.
4. **High trust, low churn** — tailors have long client relationships. Once a tool is in their workflow, they don't switch.
5. **Word of mouth** — tailor communities are tight. One strong advocate spreads it.

### The workflow problem you're solving
A tailor today:
1. Schedules an in-person fitting
2. Measures client manually (~15–20 min)
3. Records on paper or in their head
4. Loses the record when the client returns years later

Your tool:
1. Client takes 4 photos at home
2. Tailor receives a digital measurement profile
3. Profile persists, updates over time
4. Remote clients become possible

### The bigger unlock: remote clients
A tailor in New York can take a client in Austin. This is currently impossible at tailor precision. That's a market expansion story, not just an efficiency story.

---

## Business Model Options

| Model | Pros | Cons |
|---|---|---|
| SaaS per tailor (monthly fee) | Predictable revenue, simple | Small market, slow growth |
| Per-measurement fee | Aligns with usage, low barrier to try | Unpredictable, hard to forecast |
| B2B API (sell to clothing brands) | Large contracts, high ACV | Long sales cycles, custom integrations |
| Consumer app (sell to end users) | Large TAM | Low revenue per user, high CAC, low retention |
| Hybrid: tailor tool + brand API | Best of both | Complex to execute early |

**Recommendation for early stage:** SaaS per tailor. Simple, direct, gives you the data flywheel. Graduate to brand API once accuracy is proven and you have a dataset.

---

## Risks

1. **Accuracy gap** — if you can't hit ±0.25in reliably, the value prop collapses. The technical problem is unsolved (see brainstorm.md).
2. **Data cold start** — the model improves with data but needs data to be useful. Chicken-and-egg. Mitigated by: manual measurement entry as fallback during early adoption.
3. **3DLOOK moving down-market** — if a funded competitor decides to target independent tailors, they can outspend you. Mitigation: move fast, build community loyalty.
4. **Tailor adoption** — older demographic, often resistant to new tools. Distribution strategy matters as much as product quality.
5. **Liability** — if a garment is made wrong because your measurements were off, who is responsible? Needs a terms of service answer before launch.

---

## What Needs Actual Research

- [ ] Verified TAM for custom/made-to-measure clothing (current year)
- [ ] Number of independent tailors and small clothiers in target markets (US, EU to start)
- [ ] Current willingness-to-pay interviews — talk to 10 tailors before building anything
- [ ] 3DLOOK and Bodygram pricing (not publicly listed — requires sales contact or industry sources)
- [ ] Return rate data sourced from a primary report (NRF, Shopify, McKinsey)
- [ ] Regulatory considerations for biometric data (body measurements may qualify in some jurisdictions)
- [ ] Whether any VC has funded a direct competitor targeting independent tailors specifically

---

## Next Step Before Taking This Seriously

Talk to 10 independent tailors. Ask:
1. How do you currently take and store measurements?
2. Have you ever lost a client's measurements?
3. Do you have remote clients? Would you want them?
4. Would you pay for a tool that did X? How much?

That's the only research that actually matters at this stage.
