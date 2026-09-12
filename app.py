from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from dotenv import load_dotenv
from semantic_engine import SemanticEngine
from rag_pipeline import RAGPipeline
from job_fetcher import fetch_all_jobs
from models import (create_user, get_user, verify_password,
                    update_category_score, add_saved_job,
                    add_rejected_job, add_search_history, get_top_categories)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")

ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

engine = SemanticEngine()
rag    = RAGPipeline()


# ── Helper — check if user is logged in ──
def is_logged_in():
    return "username" in session


# ════════════════════════════════════════
# AUTH ROUTES
# ════════════════════════════════════════

@app.route('/register', methods=['GET', 'POST'])
def register():
    if is_logged_in():
        return redirect(url_for('home'))

    if request.method == 'POST':
        username       = request.form.get('username', '').strip()
        password       = request.form.get('password', '').strip()
        skills         = [s.strip() for s in request.form.get('skills', '').split(',') if s.strip()]
        experience     = request.form.get('experience', 'entry level')
        location       = request.form.get('location', 'remote')
        preferred_work = request.form.getlist('preferred_work')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        success, message = create_user(username, password, skills,
                                       experience, location, preferred_work)
        if success:
            session['username'] = username
            flash('Account created! Welcome.', 'success')
            return redirect(url_for('home'))
        else:
            flash(message, 'error')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if verify_password(username, password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ════════════════════════════════════════
# MAIN SEARCH ROUTE
# ════════════════════════════════════════

@app.route('/', methods=['GET', 'POST'])
def home():
    if not is_logged_in():
        return redirect(url_for('login'))

    jobs               = []
    query              = ""
    ai_recommendations = None
    username           = session['username']
    user               = get_user(username)

    if request.method == 'POST':
        query = request.form.get('query', '').strip()

        if query:
            # Build enriched query using user context
            skills_str  = ', '.join(user.get('skills', []))
            experience  = user.get('experience', '')
            enriched    = f"job search: {query}. Skills: {skills_str}. Level: {experience}."

            # Fetch jobs from both APIs
            jobs = fetch_all_jobs(query, ADZUNA_APP_ID, ADZUNA_APP_KEY)

            if jobs:
                # Semantic ranking
                query_vector = engine.encode(enriched)
                job_texts    = [f"{j['title']}. {j['description']}" for j in jobs]
                job_vectors  = engine.batch_encode(job_texts)

                for job, vector in zip(jobs, job_vectors):
                    job['similarity_score'] = engine.similarity(query_vector, vector)

                # Filter out rejected jobs
                rejected = user.get('rejected_jobs', [])
                jobs = [j for j in jobs if j['title'] not in rejected]

                jobs.sort(key=lambda j: j['similarity_score'], reverse=True)

                # Normalize scores
                if jobs:
                    top = jobs[0]['similarity_score']
                    for job in jobs:
                        job['normalized_score'] = (job['similarity_score'] / top) * 100

                # RAG recommendations
                ai_recommendations = rag.run(query, jobs)

            # Save search to history
            add_search_history(username, query)

    return render_template('index.html',
                           jobs=jobs,
                           query=query,
                           ai_recommendations=ai_recommendations,
                           user=user)


# ════════════════════════════════════════
# SAVE / REJECT ROUTES
# ════════════════════════════════════════

@app.route('/save_job', methods=['POST'])
def save_job():
    if not is_logged_in():
        return redirect(url_for('login'))

    username = session['username']
    job = {
        'title':      request.form.get('title'),
        'company':    request.form.get('company'),
        'url':        request.form.get('url'),
        'source':     request.form.get('source'),
        'category':   request.form.get('category', 'general'),
    }
    category = job['category']

    add_saved_job(username, job)
    update_category_score(username, category, +1)

    return redirect(request.referrer or url_for('home'))


@app.route('/reject_job', methods=['POST'])
def reject_job():
    if not is_logged_in():
        return redirect(url_for('login'))

    username  = session['username']
    job_title = request.form.get('title')
    category  = request.form.get('category', 'general')

    add_rejected_job(username, job_title)
    update_category_score(username, category, -1)

    return redirect(request.referrer or url_for('home'))


# ════════════════════════════════════════
# FOR YOU FEED
# ════════════════════════════════════════

@app.route('/feed')
def feed():
    if not is_logged_in():
        return redirect(url_for('login'))

    username       = session['username']
    user           = get_user(username)
    top_categories = get_top_categories(username, n=3)
    feed_jobs      = []

    if top_categories:
        for category in top_categories:
            jobs = fetch_all_jobs(category, ADZUNA_APP_ID, ADZUNA_APP_KEY)
            feed_jobs.extend(jobs[:5])

        # Remove rejected jobs
        rejected  = user.get('rejected_jobs', [])
        feed_jobs = [j for j in feed_jobs if j['title'] not in rejected]

        # Deduplicate
        seen      = set()
        unique    = []
        for job in feed_jobs:
            key = job['title'] + job['company']
            if key not in seen:
                seen.add(key)
                unique.append(job)
        feed_jobs = unique

    return render_template('feed.html',
                           feed_jobs=feed_jobs,
                           top_categories=top_categories,
                           user=user)


# ════════════════════════════════════════
# PROFILE ROUTE
# ════════════════════════════════════════

@app.route('/profile')
def profile():
    if not is_logged_in():
        return redirect(url_for('login'))
    user = get_user(session['username'])
    return render_template('profile.html', user=user)


if __name__ == '__main__':
    app.run(debug=True)