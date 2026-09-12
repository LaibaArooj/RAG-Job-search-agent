# RAG-Based Intelligent Job Search Agent
## Complete Project Log — Development Journey

**Student:** Laiba Arooj
**Supervisor:** Sir Ali Sammad
**Institution:** Department of Computer Science
**Session:** 2023 – 2027
**Last Updated:** September 7, 2026

---

## Table of Contents

1. [What I Am Building](#1-what-i-am-building)
2. [What I Want to Achieve](#2-what-i-want-to-achieve)
3. [Tech Stack and Why](#3-tech-stack-and-why)
4. [Phase 1 — Documentation](#4-phase-1--documentation)
5. [Phase 2 — Environment Setup](#5-phase-2--environment-setup)
6. [Phase 3 — Flask + Adzuna API](#6-phase-3--flask--adzuna-api)
7. [Phase 4 — Semantic Search](#7-phase-4--semantic-search)
8. [Phase 5 — RAG Pipeline](#8-phase-5--rag-pipeline)
9. [Phase 6 — Remotive API](#9-phase-6--remotive-api)
10. [Phase 7 — MongoDB + Authentication](#10-phase-7--mongodb--authentication)
11. [Bugs Fixed Along the Way](#11-bugs-fixed-along-the-way)
12. [Current File Structure](#12-current-file-structure)
13. [Current Progress Status](#13-current-progress-status)
14. [Next Steps](#14-next-steps)
15. [What I Have Learned](#15-what-i-have-learned)
16. [Viva Preparation — Key Questions and Answers](#16-viva-preparation--key-questions-and-answers)
17. [Standing Rules for This Project](#17-standing-rules-for-this-project)

---

## 1. What I Am Building

A **web application** called the **RAG-Based Intelligent Job Search Agent**. It allows users to search for remote jobs using natural, conversational language rather than exact keywords.

Instead of typing "content writer" into a search box, a user can type:

> *"I want a remote writing job that does not need any experience"*

The system understands what they mean and returns relevant jobs ranked by how closely they match — not just by whether the words appear in the listing.

### The Three AI Layers

The system has three intelligent layers stacked on top of each other:

```
Layer 1 — Semantic Search (Transformer Model)
    Converts text to meaning vectors and ranks jobs by similarity

Layer 2 — RAG Pipeline (LLM)
    Passes top jobs to an AI model which explains why each one matches

Layer 3 — Personalization (MongoDB + User Profiles)
    Learns what the user likes over time based on save/reject behavior
```

### What Makes It Different from a Normal Job Board

| Normal Job Board | This System |
|---|---|
| Keyword matching only | Meaning-based matching |
| Same results for everyone | Personalized per user |
| No explanation of results | AI explains why each job matches |
| Static rankings | Rankings improve as user interacts |

---

## 2. What I Want to Achieve

### Academic Goals
- Complete a working AI-powered web application for FYP submission
- Demonstrate understanding of LLM, Transformer, RAG, and Agent concepts in the viva
- Produce IEEE-standard SRS and SDD documentation
- Score well in both the implementation and viva components

### Technical Goals
- A fully functional web app running locally (and optionally deployed on Render.com)
- User registration and login with secure password hashing
- Natural language job search powered by sentence-transformers
- AI-generated job recommendations using Google Gemini via RAG
- A "For You" feed that learns from the user's behavior over time
- Save and Reject functionality that updates preference scores in MongoDB
- A polished, professional UI that looks impressive during the demo

### Learning Goals
- Understand how Transformer models convert text to vectors
- Understand what RAG is and why it produces better results than just asking an LLM
- Understand how Flask routes handle HTTP requests
- Understand why MongoDB is better than SQL for this specific use case
- Be able to explain every design decision in the viva with confidence

---

## 3. Tech Stack and Why

| Component | Technology | Reason for Choice |
|---|---|---|
| Backend | Python + Flask | Lightweight, easy to learn, full control |
| Database | MongoDB Atlas (free) | User data has dynamic arrays and nested objects — maps naturally to documents, one query gets everything |
| LLM | Google Gemini API (free) | Completely free with Google account, no expiry issues, model is stable |
| Embeddings | sentence-transformers (local) | Runs on laptop at zero cost, produces genuine semantic understanding |
| Job Data — Source 1 | Adzuna API (free) | 250 requests/day free, broad job listings |
| Job Data — Source 2 | Remotive API (free, no key) | Genuinely global remote jobs, companies hire from Pakistan |
| Frontend | HTML + CSS + Bootstrap 5 | No framework needed, fast to build, looks professional |
| Password Security | Werkzeug (included with Flask) | Industry standard hashing, bcrypt under the hood |
| Deployment (optional) | Render.com (free) | Free hosting, no server setup needed |

### Why NOT These Alternatives

**Why not OpenAI?** — Charges per token, requires credit card
**Why not SQL database?** — Would need 5+ joined tables for dynamic user data; MongoDB stores it all in one document
**Why not React?** — Adds too much complexity for a single developer FYP; Jinja2 + Bootstrap achieves the same visual result
**Why not local jobs from Pakistan?** — Remotive has thousands of global remote listings accessible from anywhere; local physical jobs are limited and irrelevant to the project's semantic search demonstration

---

## 4. Phase 1 — Documentation

### What Was Done
Produced two complete IEEE-standard documents before writing any code.

**SRS (Software Requirements Specification) — IEEE 830:**
- 23 Functional Requirements (FR-001 to FR-023)
- 18 Test Cases
- 5 embedded diagrams (System Context, Use Case, Class, ER, Data Flow)
- Complete sections: Introduction, Overall Description, Specific Requirements

**SDD (Software Design Document) — IEEE 1016:**
- System Overview, Architecture, Data Design, Component Design
- Human Interface Design with 4 page wireframes
- Requirements Matrix linking every FR to a SDD component
- Glossary with 11 technical definitions
- 6 UML diagram placeholders with draw.io generation prompts

### Formatting Rules (Applied to All Documents)
- Font: Times New Roman throughout
- Heading 1: 12pt bold
- Heading 2: 11pt bold
- Body text: 10pt, justified
- Line spacing: 1.5
- Numbered lists restart from 1 within each section
- TOC: LEFT tab at 1440 for titles, RIGHT tab at 9360 with dot leaders for page numbers

### Why Documentation First
Writing requirements before code forces you to think through the entire system before committing to an approach. It catches design flaws early when they are cheap to fix. It also gives the supervisor a formal basis for approving the project scope.

### Real-World Relevance
IEEE 830/1016 documentation is the formal ancestor of modern lightweight practices like user stories (Agile), architecture decision records (ADRs), and design docs used at companies like Google and Microsoft.

---

## 5. Phase 2 — Environment Setup

### What Was Done
- Created project folder `RAG-Job-Search-Agent` on L: drive
- Set up Python virtual environment
- Installed core packages
- Registered for Adzuna API
- Created `.env` file for secrets

### Issues Encountered and Fixed

**Problem 1 — venv symlink error on Windows:**
```
Unable to copy 'venvlauncher.exe'
```
**Fix:**
```bash
python -m venv venv --copies
```
The `--copies` flag physically copies files instead of creating symlinks, bypassing Windows permission restrictions.

**Problem 2 — PowerShell blocked activation script:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```
`-Scope Process` only changes policy for the current terminal session — safe.

**Problem 3 — Folder name had spaces:**
Renamed from `RAG-Job search agent` to `RAG-Job-Search-Agent`. Spaces in paths cause subtle bugs in command-line tools.

### .env File Structure
```
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key
GEMINI_API_KEY=your_gemini_key
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
SECRET_KEY=fyp2026jobsearchsecret
```

### Adzuna Registration Settings
- Application type: **Personal or academic research**
- Monthly visitors: **0-10**
- Primary market: **Pakistan**
- Primary industry: **Education**

### Why .env Files Matter
Environment variables keep secrets out of source code. This is part of the "12-Factor App" methodology followed by companies using AWS, Heroku, Docker, and Kubernetes. If secrets were hardcoded in Python files, they would be visible to anyone who sees the code — especially dangerous if pushed to GitHub.

---

## 6. Phase 3 — Flask + Adzuna API

### What Was Built
- Flask app running at localhost:5000
- Search form accepting a text query
- Adzuna API call returning real live job listings
- Bootstrap job cards displaying title, company, location, description, link

### Key Code Concept — Flask Route
```python
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        query = request.form.get('query', '')
        # call API, return results
    return render_template('index.html', jobs=jobs)
```
- `GET` serves the empty search page
- `POST` processes the submitted form and returns results
- Same URL handles both — this is standard REST convention

### What Was Learned
- `request.form.get('query', '')` reads the value the user typed in the search box
- `response.json()` converts the API's response string into a Python dictionary
- Adzuna returns nested objects: `job['company']['display_name']`
- Jinja2 templating: `{% for job in jobs %}` loops through results in HTML
- The "WARNING: development server" message is normal — only matters for public deployment

### Real-World Relevance
Calling a third-party REST API and rendering the JSON response in a web page is one of the most common tasks in backend web development. Travel sites (flights from airline APIs), e-commerce (prices from supplier APIs), and weather apps all use this exact pattern.

---

## 7. Phase 4 — Semantic Search

### What Was Built
- `semantic_engine.py` — a reusable class wrapping the sentence-transformers model
- Integration into `app.py` so every search is semantically ranked
- Match percentage badges on each job card (normalized so top result = 100%)

### The SemanticEngine Class
```python
class SemanticEngine:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dim = 384

    def encode(self, text):           # text → 384-dim vector
    def batch_encode(self, texts):    # list of text → list of vectors (faster)
    def similarity(self, vec1, vec2): # cosine similarity → float 0 to 1
```

### How Semantic Search Works
1. User types "remote writing job no experience"
2. `encode()` converts this to a 384-number vector like `[0.23, -0.14, 0.87, ...]`
3. Each job's title + description is also encoded to a vector
4. `similarity()` measures how close each job vector is to the query vector
5. Jobs are sorted by score — most similar first

### Why 50% Match Score Is Normal
Cosine similarity between a short query and a long job description rarely exceeds 60-70% even for a perfect match. What matters is the **ranking order**, not the absolute score. The display was normalized so top result always shows 100%.

### What Was Learned
- Transformer models understand meaning, not just words — "remote copywriter" matches "work from home writing content" even with zero word overlap
- Embeddings are a way to turn meaning into math — two similar meanings produce vectors that are mathematically close
- `batch_encode()` is much faster than encoding one job at a time because it processes them in parallel on the GPU/CPU

### Real-World Relevance
Semantic search is used by Google Search (since 2019 BERT update), LinkedIn job matching, Spotify song recommendations, and Netflix content recommendations. sentence-transformers specifically is used in production by companies building internal document search, customer support systems, and e-commerce product discovery.

---

## 8. Phase 5 — RAG Pipeline

### What Was Built
- `rag_pipeline.py` — RAGPipeline class using Google Gemini
- Integration into search route so top 5 jobs get passed to the LLM
- Yellow "AI Recommendations" box displaying Gemini's picks with explanations

### What RAG Means
```
Retrieval    → Fetch top 5 semantically ranked jobs from APIs
Augmented    → Add those jobs as context in the LLM prompt
Generation   → LLM reads the context and generates recommendations
```

The LLM does NOT search the internet. It only sees what we give it. This grounds the response in real, current data rather than the model's training data.

### The RAGPipeline Class
```python
class RAGPipeline:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-3.6-flash")
        self.top_k = 5

    def build_prompt(self, query, jobs):
        # Combines user query + top job listings into a structured prompt

    def run(self, query, jobs):
        # Calls Gemini, returns recommendation text
        # Returns None gracefully if API fails — app never crashes
```

### LLM Provider Journey
Originally used Groq API (Llama 3). Models kept getting deprecated:
- `llama3-8b-8192` → decommissioned
- `llama-3.1-8b-instant` → removed from free tier
- Switched to **Google Gemini** — more stable, free forever with Google account
- Final model: `gemini-3.6-flash`

### What Was Learned
- LLMs work best when given structured context (job title, company, description) rather than asking them to search themselves
- The prompt format matters enormously — specifying "format exactly like this: 1. [Title] at [Company] - [explanation]" produces consistent, parseable output
- Error handling in AI pipelines is critical — the system must never crash if the LLM is unavailable
- `temperature=0.3` produces more focused, consistent responses (lower = more deterministic)

### Real-World Relevance
RAG is the most widely adopted pattern for building production LLM applications. Used by Microsoft Copilot, GitHub Copilot, Notion AI, and virtually every enterprise AI product. The alternative (fine-tuning the model) costs hundreds of thousands of dollars and becomes outdated quickly.

---

## 9. Phase 6 — Remotive API

### Why Added
Adzuna UK jobs often say "must be UK-based" even for remote listings. Real remote-friendly jobs needed.

### What Was Built
`job_fetcher.py` — combines Adzuna and Remotive into a normalized common format

```python
{
    "title":       "Content Writer",
    "company":     "XYZ Company",
    "location":    "Remote — Worldwide",
    "description": "...",
    "url":         "https://...",
    "salary":      None,
    "source":      "Remotive"   # or "Adzuna"
}
```

Remotive is free, needs no API key, and specifically lists companies that hire internationally from anywhere including Pakistan.

### Source Badge
Each job card shows a grey source badge — "Remotive" or "Adzuna" — so users and the examiner can see which API the job came from.

### What Was Learned
- Normalizing multiple API responses into a single common format is called "data normalization" — essential when combining data sources
- Deduplication by title + company prevents the same job appearing twice in results
- `striptags` Jinja2 filter removes HTML from Remotive descriptions since they return HTML rather than plain text

---

## 10. Phase 7 — MongoDB + Authentication

### What Was Built
- MongoDB Atlas free cluster set up
- `models.py` with all database functions
- User registration with hashed passwords
- User login with session management
- Redirect unauthenticated users to login page
- Save job → updates MongoDB + increments category score
- Reject job → updates MongoDB + decrements category score
- For You feed generated from top-scoring categories
- Profile page showing skills, scores, and saved jobs

### MongoDB Setup Steps
1. Account created at mongodb.com/atlas with Google login
2. Free M0 cluster on AWS Mumbai (closest to Pakistan)
3. Database user `laibaаrooj201_db_user` created
4. IP whitelist: `0.0.0.0/0` (allow all — safe for development)
5. Connection string added to `.env` as `MONGO_URI`

### The User Document Structure
```json
{
    "username":        "laiba",
    "password":        "hashed_string_here",
    "skills":          ["Python", "Writing", "Excel"],
    "experience":      "entry level",
    "location":        "Pakistan",
    "preferred_work":  ["remote", "freelance"],
    "category_scores": { "remotive": 5, "adzuna": -1 },
    "search_history":  ["remote writing job", "content creator"],
    "saved_jobs":      [{ "title": "...", "company": "...", "url": "..." }],
    "rejected_jobs":   ["Senior Java Engineer"],
    "created_at":      "2026-08-24T..."
}
```

### How Preference Scores Work
```
User saves a writing job     → writing score + 1
User rejects a tech job      → tech score - 1
User visits For You feed     → system finds top 3 positive-score categories
                             → fetches and displays jobs from those categories
```

This is a simplified version of content-based filtering — the same technique used by Netflix, Spotify, and YouTube.

### Key Security Points
- Passwords NEVER stored as plain text — always hashed with Werkzeug (bcrypt)
- API keys stored in `.env`, never in Python source files
- Flask `session` stores only the username — not the password or any sensitive data
- `secret_key` required to sign session cookies so they cannot be tampered with

### Why MongoDB Over SQL
| Situation | MongoDB | SQL |
|---|---|---|
| skills (varies per user) | Array in same document | Separate SKILLS table + JOIN |
| category_scores (new categories added dynamically) | Dynamic Object field | Would require schema change |
| saved_jobs (nested objects) | Embedded array | Separate SAVED_JOBS table + JOIN |
| Get complete user profile | 1 query | 4+ JOINs across tables |

---

## 11. Bugs Fixed Along the Way

| Bug | Error Message | Cause | Fix |
|---|---|---|---|
| Jinja undefined error | `'job' is undefined` | `{{ job.title }}` placed before `{% for job in jobs %}` loop | Moved d-flex div inside the for loop |
| HTML tags in descriptions | `<p>CT Marketing...</p>` showing on page | Remotive returns HTML in description field | Added `\| striptags` Jinja filter |
| Duplicate LLM recommendations | Same job appearing twice in AI box | Adzuna returning duplicate listings | Added deduplication set before passing to RAG |
| Groq model decommissioned | `llama3-8b-8192 does not exist` | Groq retired the model | Switched to Google Gemini |
| Gemini wrong model name | `gemini-1.5-flash is not found` | Model name changed | Used `genai.list_models()` to find correct name, settled on `gemini-3.6-flash` |
| venv creation error | `Unable to copy venvlauncher.exe` | Windows symlink permissions | Added `--copies` flag to venv creation |
| PowerShell blocked | `execution of scripts is disabled` | PowerShell security policy | Used `-Scope Process` execution policy |

---

## 12. Current File Structure

```
RAG-Job-Search-Agent/
│
├── venv/                      ← Python virtual environment (do not edit)
│
├── templates/
│   ├── login.html             ← Login page
│   ├── register.html          ← Registration page with profile setup
│   ├── index.html             ← Main search page with job cards + AI box
│   ├── feed.html              ← For You personalized feed
│   └── profile.html           ← User profile and preference scores
│
├── .env                       ← All API keys and secrets (never commit to Git)
├── app.py                     ← Flask routes and main pipeline orchestration
├── models.py                  ← MongoDB connection and all database functions
├── semantic_engine.py         ← SemanticEngine class (Transformer encoding)
├── rag_pipeline.py            ← RAGPipeline class (Gemini LLM integration)
├── job_fetcher.py             ← fetch_all_jobs (Adzuna + Remotive unified)
├── test_semantic.py           ← Standalone semantic search test
└── test_groq.py               ← Groq connection test (now using Gemini)
```

---

## 13. Current Progress Status

| Phase | Feature | Status |
|---|---|---|
| 1 | SRS document (IEEE 830) | ✅ Complete |
| 1 | SDD document (IEEE 1016) | ✅ Complete |
| 2 | Environment setup (venv, packages, .env) | ✅ Complete |
| 3 | Flask app running locally | ✅ Complete |
| 3 | Adzuna API live job search | ✅ Complete |
| 4 | Semantic ranking (sentence-transformers) | ✅ Complete |
| 4 | Match percentage badges | ✅ Complete |
| 5 | RAG pipeline (Gemini AI) | ✅ Complete |
| 5 | AI Recommendations box | ✅ Complete |
| 6 | Remotive API (global remote jobs) | ✅ Complete |
| 6 | Source badges on job cards | ✅ Complete |
| 7 | MongoDB Atlas setup | ✅ Complete |
| 7 | User registration + login | ✅ Complete — needs testing |
| 7 | Save/Reject + preference scores | ✅ Code written — needs testing |
| 7 | For You personalized feed | ✅ Code written — needs testing |
| 7 | Profile page | ✅ Code written — needs testing |
| 8 | UI redesign (polished, attractive) | ❌ Not started |
| 8 | AI Agent layer (intent parsing) | ❌ Not started |
| 8 | Autocomplete suggestions | ❌ Not started |
| 8 | Filters (job type, experience) | ❌ Not started |
| 8 | Testing all features end-to-end | ❌ Not started |
| 8 | Final project documentation update | ❌ Not started |
| 8 | Viva preparation | ⏳ Ongoing |

---

## 14. Next Steps

### Immediate — This Week
1. **Test MongoDB auth system** — run `python app.py`, register a new account, login, search, save a job, reject a job. Confirm everything reaches MongoDB
2. **Verify For You feed** — save 3-4 jobs from a category, visit /feed, check if relevant jobs appear
3. **Check profile page** — confirm preference scores update when you save/reject

### Short Term — Before Semester Starts
4. **UI redesign** — replace plain Bootstrap styling with a professional, polished design. Custom CSS, proper color scheme, animations, attractive job cards
5. **Add autocomplete** — search suggestions appearing as user types based on past searches and categories
6. **Add filters** — dropdowns for job type (remote/hybrid) and experience level

### Medium Term — During Semester
7. **AI Agent layer** — smarter intent parsing from natural language (extract job type, location, experience level from the query automatically)
8. **Context injection** — user's skills and experience level injected into every search query before encoding (already partially done)
9. **Final end-to-end testing** — test every feature with multiple user accounts
10. **Optional deployment** — push to Render.com for a live demo URL

### Documentation
11. **Update progress log** — add entries for MongoDB phase and UI redesign
12. **Update SDD** — fill in draw.io diagram placeholders with actual exported images
13. **Prepare project report** — using documentation log entries as the basis

---

## 15. What I Have Learned

### Concept 1 — What a Transformer Model Actually Does
A Transformer takes text and converts it to a list of 384 numbers. These numbers represent the *meaning* of the text in a mathematical space. Two pieces of text with similar meaning will produce number lists that are close together in this space. This is how semantic search works — measuring mathematical closeness rather than word matching.

### Concept 2 — What RAG Is and Why It Matters
Without RAG, if you ask an LLM "what are the best writing jobs available today?" it makes things up based on its training data (which might be years old). With RAG, you first fetch real current job listings from APIs, then include them in the prompt. The LLM then responds based on actual real data, not its imagination. This is why RAG is the standard approach for production AI applications.

### Concept 3 — Why MongoDB Over SQL for This Project
The user's preference scores are a dynamic object — new categories get added as the user interacts. In SQL, adding a new category would require altering the database schema. In MongoDB, you just write a new key-value pair into the existing document. The entire user profile — skills, preferences, saved jobs, scores, history — is retrieved in one single database query.

### Concept 4 — Flask Request Cycle
Every time a user clicks Search, their browser sends an HTTP POST request to Flask. Flask processes it, calls the APIs, runs the AI pipeline, and sends back an HTML response. This cycle — request → process → response — is the foundation of all web applications everywhere.

### Concept 5 — Password Security
Passwords must never be stored as plain text. Werkzeug's `generate_password_hash()` runs the password through bcrypt, producing a completely different string. When the user logs in again, `check_password_hash()` runs the same process on the entered password and compares the result. Even if someone steals the database, they get hashed strings that are computationally impossible to reverse.

### Concept 6 — API Keys and Security
API keys stored in `.env` files follow the "12-Factor App" principle. Keys in source code get accidentally pushed to GitHub and stolen by bots within minutes. Keys in environment variables stay on the server only.

### Concept 7 — The Difference Between SRS and SDD
The SRS answers WHAT — what must the system do, what are the requirements. The SDD answers HOW — how will it be built, what classes, what database structure, what algorithms. The same diagram type (Class Diagram, ER Diagram) appears in both but at different levels of detail.

---

## 16. Viva Preparation — Key Questions and Answers

**Q: What type of system did you build?**
A: A web application. The frontend is HTML/CSS/Bootstrap 5 in the browser. The backend is Python and Flask handling all logic, API calls, and database operations. The database is MongoDB Atlas hosted in the cloud. Everything runs locally during development.

**Q: What makes this different from a normal job board?**
A: A normal job board uses keyword matching — if you type "writer" it finds jobs containing the word "writer." My system uses semantic search — it understands meaning. Searching "I want to work from home creating content" finds "Remote Copywriter" even with zero word overlap, because both phrases have similar meaning when encoded as vectors.

**Q: What is RAG and how does your system use it?**
A: RAG stands for Retrieval-Augmented Generation. The system first retrieves the top 5 semantically ranked jobs from real APIs (Retrieval), includes them as context in the LLM prompt (Augmented), then the LLM generates plain-English recommendations explaining why each job matches (Generation). The LLM only sees what we give it — it does not search the internet. This grounds the response in real, current job data.

**Q: Why did you choose MongoDB over a relational database?**
A: The user's context profile contains variable-length arrays (skills, saved jobs), a dynamic key-value object (category scores that grow as the user interacts), and nested objects. Storing this in SQL would require 5+ joined tables. MongoDB stores the entire user profile as one document that can be retrieved in a single query. The dynamic category_scores field specifically cannot be done cleanly in SQL without altering the schema every time a new category appears.

**Q: Why does the same diagram (Class, ER) appear in both SRS and SDD?**
A: The SRS diagram is at the conceptual level — what classes or entities exist and broadly how they relate. The SDD diagram adds implementation detail — exact data types, primary keys, foreign keys, method parameters, multiplicities — everything a developer needs to write actual code. The standard requires this distinction.

**Q: What is cosine similarity?**
A: It measures how close two vectors are in mathematical space, regardless of their length. A score of 1.0 means the vectors point in exactly the same direction — identical meaning. A score of 0.0 means completely unrelated. In the system, the query vector and each job's vector are compared using cosine similarity, and jobs are sorted by this score from highest to lowest.

**Q: Why are the match scores around 50%? Is that good?**
A: Yes, 50% is good. Cosine similarity between a short query (6 words) and a long job description (200 words) rarely exceeds 60-70% even for a perfect semantic match. The absolute value does not matter — what matters is the ranking order. The display is normalized so the top result always shows 100% and others are relative to it.

**Q: What happens if the LLM API is unavailable?**
A: The system falls back gracefully. The `run()` method in RAGPipeline is wrapped in a try/except block. If the Gemini API returns an error, the method returns None. The Flask route checks if `ai_recommendations` is None, and if so, simply does not render the AI Recommendations box. The user still sees all the semantically ranked job results — they just don't get the AI explanations. The app never crashes.

**Q: Why remote jobs only? What about local Pakistan jobs?**
A: This was a deliberate design decision. The Remotive API provides genuinely global remote positions where companies hire internationally regardless of location — these are actually more accessible and better-paying for Pakistani graduates than local physical listings which are limited in number. The scope also makes the semantic search demonstration more impactful since there are thousands of diverse remote listings to rank.

**Q: How does the For You feed personalize results?**
A: Every time a user saves a job, the system increments a preference score for that job's category by +1 in MongoDB. Every time they reject a job, the score decrements by -1. When the user visits the For You tab, the system reads their category_scores, finds the top 3 positive-scoring categories, and fetches jobs specifically from those categories. This is a simplified form of content-based filtering — the same technique used by Netflix, Spotify, and YouTube to generate recommendations.

---

## 17. Standing Rules for This Project

These apply to every development session going forward:

1. **UI must be polished and attractive** — not default Bootstrap. Custom CSS, proper colors, animations, professional layout. Plain styling is not acceptable for the demo.

2. **Flag complex tasks for Fable 5** — before attempting hard multi-file AI core tasks, consider using Fable 5 on the other account which is better for long autonomous multi-file coding sessions.

3. **Update this document after every major step** — add a new entry covering what was done, how, why, what was learned, and real-world relevance.

4. **Test standalone before wiring in** — always test a new component in isolation (like test_groq.py, test_semantic.py) before connecting it to the Flask app. This makes debugging dramatically easier.

5. **Never hardcode API keys** — always use `.env` and `os.getenv()`.

6. **Error handling on all AI calls** — every API call must be wrapped in try/except. The app must never crash because an external service is unavailable.

---

*This document is a living record — it will be updated as development progresses through UI redesign, AI Agent layer, testing, and final report writing.*

