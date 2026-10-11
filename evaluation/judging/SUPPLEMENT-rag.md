# RAG-stage supplement — judging sheet

42 candidates that no earlier sheet showed. They are needed for the all-sources
RAG-stage comparison (`evaluation/queries.md` § 8). Nothing on this sheet says which
jobs the LLM picked, and nothing could: the candidates were chosen without calling it.

**Status:** marked

Change `unmarked` to `marked` when every card is done. `score_rag.py` refuses to score
until then, because a blank box would otherwise be read as a verdict.

Mark each `[x]` if RELEVANT under R1–R5 in `evaluation/queries.md` § 3, **read with the
clarifications C1–C4 in § 7**. Leave `[ ]` if not. When a rule is genuinely ambiguous,
leave it unmarked and note why.

Reminder: eligibility is NOT part of relevance. Judge the role, not whether the
employer would hire you from your country.

Also note any listing that is the SAME vacancy as another in its query (C3's
definition), so the pair can be declared in § 8.2 before scoring.

---

## Q01 — `something creative I can do from my bedroom`

### Q01.1. Senior Full Stack Engineer

- **Company:** Fueled
- **Location:** Remote
- Location: Remote — (Open to applicants located anywhere around the globe) Fueled is a leading digital strategy, design, and engineering agency. We are a 300+ person team that has designed and built hundreds of digital products and experienc

- [ ] relevant

Note: R2 — full-stack engineering, not a creative role someone would click on for this query.

### Q01.2. Contract Senior Front End Engineer

- **Company:** Fueled
- **Location:** Remote
- Location: Remote — Anywhere (Open to applicants located anywhere around the globe) Fueled is a leading digital strategy, design, and engineering agency. We are a 300+ person team that has designed and built hundreds of digital products and 

- [ ] relevant

Note: R2 — front-end engineering, not a creative role.

## Q02 — `a job where I help people all day`

### Q02.1. Solution Engineer

- **Company:** RelationalAI
- **Location:** Remote
- Who We Are At RelationalAI, we’re solving one of the most important challenges in artificial intelligence: how to teach large language models the logic, semantics, and business context of the modern enterprise. Frontier models are trained a

- [ ] relevant

Note: R2 genuinely ambiguous, so not relevant per the tie-break. Pre-sales technical solution engineering is customer-facing but not clearly "help people all day".

## Q06 — `junior frontend developer react remote`

### Q06.1. Software Engineer - Auth

- **Company:** Supabase
- **Location:** Remote
- About Supabase Supabase is the Postgres development platform, built by developers for developers. We provide a complete backend solution including Database, Auth, Storage, Edge Functions, Realtime, and Vector Search. All services are deeply

- [ ] relevant

Note: R2 — auth/backend engineering, not frontend/React.

### Q06.2. Ubuntu Engineering Lead

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R3 — Lead contradicts "junior". R2 — not frontend.

### Q06.3. Postgres Engineer

- **Company:** Supabase
- **Location:** Remote
- Supabase is the Postgres development platform, built by developers for developers. We provide a complete backend solution including Database, Auth, Storage, Edge Functions, Realtime, and Vector Search. All services are deeply integrated and

- [ ] relevant

Note: R2 — database engineering, not frontend/React.

## Q08 — `graphic designer figma branding`

### Q08.1. Creative (Motion Design)

- **Company:** Superside
- **Location:** Remote
- Superside is looking for a motion designer with the creativity, technical expertise, and innovation mindset to push the boundaries of motion design. You’ll work with top global brands, crafting high-impact motion graphics, animated digital 

- [x] relevant

Note: R2 — brand-facing visual design work a graphic-designer query would plausibly click. Borderline (motion design is not graphic design, no Figma or branding mentioned), but silence is not a contradiction.

### Q08.2. Senior Full Stack Engineer

- **Company:** Fueled
- **Location:** Remote
- Location: Remote — (Open to applicants located anywhere around the globe) Fueled is a leading digital strategy, design, and engineering agency. We are a 300+ person team that has designed and built hundreds of digital products and experienc

- [ ] relevant

Note: R2 — engineering, not design.

### Q08.3. Conceptual Copywriter

- **Company:** Superside
- **Location:** Remote
- Superside is looking for a talented Conceptual Copywriter to ideate and execute impactful creative work across digital campaigns and marketing channels. In this role, you’ll partner with designers, strategists, and performance teams to deve

- [ ] relevant

Note: R2 — copywriting, not graphic design.

### Q08.4. Product Growth Strategist

- **Company:** Fueled
- **Location:** Remote
- Location: Remote — Anywhere (Open to applicants located anywhere around the globe) Fueled is a leading digital strategy, design, and engineering agency. We are a 300+ person team that has designed and built hundreds of digital products and 

- [ ] relevant

Note: R2 — growth strategy, not design.

### Q08.5. Python and Kubernetes Software Engineer - Data, Workflows, AI/ML & Analytics

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R2 — engineering, not design.

## Q11 — `entry level marketing role no degree required`

### Q11.1. Senior Performance Marketer (Full Remote - Worldwide)

- **Company:** EverAI
- **Location:** Remote
- Our Vision & Products EverAI — Building the Future of AI Companionship One of the Top 15 Largest & Fastest-Growing AI Companies in the World 50 Million Users in 2 years — Help Us Reach 100M first, 500M next At EverAI, we’re shaping what it 

- [ ] relevant

Note: R3 — Senior contradicts "entry level".

### Q11.2. Conceptual Copywriter

- **Company:** Superside
- **Location:** Remote
- Superside is looking for a talented Conceptual Copywriter to ideate and execute impactful creative work across digital campaigns and marketing channels. In this role, you’ll partner with designers, strategists, and performance teams to deve

- [X] relevant

Note (re-judged 2026-10-11, card only, before scoring): relevant. A copywriter on marketing campaigns is a plausible click for an entry-level marketing query (R2), and the card is silent on seniority and degree, so R3 and C1 pass. The first reading, made against the live posting on external job boards, which states 4+ years of experience, was not relevant. That reading is reported as a sensitivity check (queries.md § 8.6), because every other verdict was made on the card alone.

### Q11.3. Enterprise Account Executive

- **Company:** Canonical
- **Location:** Remote
- This is a general track role, hiring for opportunities across all levels of seniority in our Sales Teams.Apply here if you believe you possess outstanding revenue generating experience from the Technology industry. Open source software is t

- [ ] relevant

Note: R2 — sales, not marketing. R3 — asks for outstanding revenue-generating experience, contradicting "entry level".

### Q11.4. Account Director

- **Company:** Superside
- **Location:** Remote
- Superside is hiring an Account Director to lead and grow a portfolio of strategically important enterprise customers. You’ll own the full customer lifecycle, from pre-sale scoping through delivery, renewal, and expansion, ensuring customers

- [ ] relevant

Note: R2 — account management, not marketing. R3 — Director level contradicts "entry level".

### Q11.5. Community Engineer (multiple roles and seniority levels)

- **Company:** Canonical
- **Location:** Remote
- Our ambition is to set a standard of excellence when it comes to serving the open source ecosystem. This is your chance to be a part of that as a Community Engineer at Canonical.We are building community management at scale. We have multipl

- [ ] relevant

Note: R2 — community engineering, not marketing. Multi-role, multi-level posting; fails on R2 regardless.

## Q12 — `part time customer support work from home`

### Q12.1. Product Lead - Infrastructure

- **Company:** Supabase
- **Location:** Remote
- Supabase is the open-source Postgres development platform that 10M+ developers and thousands of enterprises depend on every day. Database, Auth, Storage, Edge Functions, Realtime and Vector Search all run on one platform: the same compute, 

- [ ] relevant

Note: R2 — product leadership, not customer support.

### Q12.2. Product Manager - Marketplace

- **Company:** Supabase
- **Location:** Remote
- Supabase is the open-source Postgres development platform that 7M+ developers and thousands of enterprises depend on every day. We provide a complete backend solution including Database, Auth, Storage, Edge Functions, Realtime, and Vector S

- [ ] relevant

Note: R2 — product management, not customer support.

### Q12.3. Postgres Engineer

- **Company:** Supabase
- **Location:** Remote
- Supabase is the Postgres development platform, built by developers for developers. We provide a complete backend solution including Database, Auth, Storage, Edge Functions, Realtime, and Vector Search. All services are deeply integrated and

- [ ] relevant

Note: R2 — database engineering, not customer support.

### Q12.4. Cloud Professional Services Manager

- **Company:** Canonical
- **Location:** Remote
- This is an opportunity to run a Professional Services team (also known as Field Engineering) team, helping customers understand and implement Canonical's open source solutions in public clouds and in their own data centers. We work across t

- [ ] relevant

Note: R2 — management of a professional services team, not customer support. Customer-facing, but not support work.

### Q12.5. Conceptual Copywriter

- **Company:** Superside
- **Location:** Remote
- Superside is looking for a talented Conceptual Copywriter to ideate and execute impactful creative work across digital campaigns and marketing channels. In this role, you’ll partner with designers, strategists, and performance teams to deve

- [ ] relevant

Note: R2 — copywriting, not customer support.

## Q14 — `remote data entry job that hires worldwide`

### Q14.1. Cloud Field Engineer

- **Company:** Canonical
- **Location:** Remote
- Help global companies embrace the latest private cloud infrastructure, Linux and cloud native operations, and open source applications. Our team applies expert insights to real-world customer problems, enabling the enterprise adoption of Li

- [ ] relevant

Note: R2 — field engineering, not data entry.

### Q14.2. Embedded Linux Field Engineer for Devices/IoT

- **Company:** Canonical
- **Location:** Remote
- Job DescriptionCanonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cl

- [ ] relevant

Note: R2 — embedded Linux engineering, not data entry.

### Q14.3. Senior Software Engineer, Backend (Money Movement)

- **Company:** Phantom
- **Location:** Remote
- Phantom is on a mission to connect the world to the freedom of open markets. Tens of millions of people all over the world use Phantom to access global markets that never close, including perpetuals, prediction markets, tokenized assets, st

- [ ] relevant

Note: R2 — backend engineering, not data entry.

### Q14.4. Python and Kubernetes Software Engineer - Data, Workflows, AI/ML & Analytics

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R2 — software engineering, not data entry, despite the "data" in the title.

## Q15 — `freelance copywriting contract short term`

### Q15.1. Dutch Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: R2 genuinely ambiguous, so not relevant per the tie-break. Listed tasks are review, translation, copy-edit, QC and machine-translation post-editing of existing sports content. Copywriting appears only as one qualifying background, not as the job. Contract basis would not fail R4. Only the Dutch posting was read in full; the other languages are assumed to share its template.

### Q15.2. Hebrew Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: same as Q15.1.

### Q15.3. Slovak Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: same as Q15.1.

### Q15.4. Ukrainian Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: same as Q15.1.

## Q16 — `job where I write stuff but not journalism`

### Q16.1. Ukrainian Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: R2 genuinely ambiguous, so not relevant per the tie-break. The role is mainly review, translation and QC of existing content rather than original writing. R5 (journalism) is moot. Judged identically with Q16.2–16.4 and Q15.1–15.4.

### Q16.2. Hebrew Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: same as Q16.1.

### Q16.3. Slovak Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: same as Q16.1.

### Q16.4. Dutch Sports Localization Specialist (Football)

- **Company:** Welo Global
- **Location:** Remote
- As a trusted global transformation partner, Welocalize accelerates the global business journey by enabling brands and companies to reach, engage, and grow international audiences. Welocalize delivers multilingual content transformation serv

- [ ] relevant

Note: same as Q16.1.

## Q17 — `not sales but still talking to customers`

### Q17.1. Senior/Staff/Principal Engineer

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R2 — nothing on the card shows customer contact; reads as an engineering role.

### Q17.2. Ubuntu Sales Engineer (Entry-Level)

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R5 — a sales role, which this query excludes.

### Q17.3. Solution Architecture Manager

- **Company:** Canonical
- **Location:** Remote
- This is an opportunity to run a field engineering team, helping customers understand and implement Canonical's open source solutions in public clouds and in their own data centers. We work across the entire spectrum of cloud offerings, from

- [x] relevant

Note: customer-facing field engineering team helping customers implement the product, not a sales role (R5). The query states no seniority, so "Manager" is not a contradiction (R3).

### Q17.4. Embedded Devices Software Solution Sales - All Roles

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R5 — a sales role, which this query excludes. Also an all-roles umbrella posting.

## Q18 — `something in HR that isn't recruitment`

### Q18.1. DevOps Engineer (Intern)

- **Company:** Mactores
- **Location:** Remote
- Mactores is the agent-native AWS modernization firm. Most modernization work doesn't ship, it stalls in pilots, slips a year, or lands at three times the budget. We exist to ship it: production systems running, legacy retired, outcomes meas

- [ ] relevant

Note: R2 — DevOps, not HR.

### Q18.2. AWS DevOps Engineer (Senior)

- **Company:** Mactores
- **Location:** Remote
- Mactores is the agent-native AWS modernization firm. Most modernization work doesn't ship, it stalls in pilots, slips a year, or lands at three times the budget. We exist to ship it: production systems running, legacy retired, outcomes meas

- [ ] relevant

Note: R2 — DevOps, not HR.

## Q19 — `coding job that isn't web development`

### Q19.1. Engineering Manager

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R2 — people management rather than a coding job. The card also doesn't state the team's domain, so the web exclusion can't be checked (R5). Not relevant either way.

## Q20 — `design work that doesn't need a portfolio`

### Q20.1. Site Reliability Engineer

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is widely used in breakthrough enterprise initiatives such as public cloud, data science, A

- [ ] relevant

Note: R2 — site reliability engineering, not design. C2: no portfolio requirement is stated, so R5 passes.

### Q20.2. Enterprise Project Manager

- **Company:** Canonical
- **Location:** Remote
- Canonical is a leading provider of open source software and operating systems to the global enterprise and technology markets. Our platform, Ubuntu, is very widely used in breakthrough enterprise initiatives such as public cloud, data scien

- [ ] relevant

Note: R2 — project management, not design. C2: no portfolio requirement is stated, so R5 passes.

---

## Judging notes

- Ticked (3): Q11.2 (card-only re-judgement), Q08.1 (brand-facing visual design; borderline, silence on Figma and branding passes) and Q17.3 (customer-facing, not sales).
- Judged against R1–R5 and C1–C4 as written in `evaluation/queries.md` §§ 3 and 7. Tie-break applied: genuinely ambiguous means not relevant.
- Ambiguous, so not relevant: Q02.1 and all eight Welocalize cards (Q15.1–15.4, Q16.1–16.4). The Welocalize cards were judged identically; only the Dutch posting was read in full.
- Q11.2: relevant on the card alone (headline). Not relevant on the external posting text (sensitivity only, § 8.6).
- Duplicates (C3): none found within a query. Welocalize titles differ by language, and shared template text does not count. No pairs to declare in § 8.2.
- Zero-relevant queries (C4): Q01, Q02, Q06, Q11, Q12, Q14, Q15, Q16, Q18, Q19, Q20 have no relevant candidate among those judged and score 0 in the mean. Q08 and Q17 have one each.
- Everything else not ticked fails R2 (role type), plus R3 on Q06.2, Q11.1, Q11.3, Q11.4 (seniority) and R5 on Q17.2, Q17.4 (sales).