from flask import Flask, render_template, request
import os
from dotenv import load_dotenv
from semantic_engine import SemanticEngine
from rag_pipeline import RAGPipeline
from job_fetcher import fetch_all_jobs

load_dotenv()

app = Flask(__name__)

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Load both AI components once at startup
engine = SemanticEngine()
rag = RAGPipeline()


@app.route('/', methods=['GET', 'POST'])
def home():
    jobs = []
    query = ""
    ai_recommendations = None

    if request.method == 'POST':
        query = request.form.get('query', '').strip()

        if query:
            # 1. Fetch from Adzuna and Remotive, normalised and deduplicated
            jobs = fetch_all_jobs(query, ADZUNA_APP_ID, ADZUNA_APP_KEY)

            if jobs:
                # 2. Semantic ranking
                enriched_query = f"job search: {query}. Looking for relevant job listings."
                query_vector = engine.encode(enriched_query)

                job_texts = [
                    f"{job['title']}. {job.get('description', '')}"
                    for job in jobs
                ]
                job_vectors = engine.batch_encode(job_texts)

                for job, vector in zip(jobs, job_vectors):
                    job['similarity_score'] = engine.similarity(
                        query_vector, vector
                    )

                jobs.sort(
                    key=lambda j: j['similarity_score'],
                    reverse=True
                )

                # Normalize scores for display, relative to the best match.
                # Cosine similarity can be zero or negative, so guard the divide.
                top_score = jobs[0]['similarity_score']
                for job in jobs:
                    if top_score > 0:
                        job['normalized_score'] = (
                            job['similarity_score'] / top_score
                        ) * 100
                    else:
                        job['normalized_score'] = 0.0

                # 3. RAG pipeline — pass top 5 to LLM
                ai_recommendations = rag.run(query, jobs)

    return render_template(
        'index.html',
        jobs=jobs,
        query=query,
        ai_recommendations=ai_recommendations
    )


if __name__ == '__main__':
    app.run(debug=True)