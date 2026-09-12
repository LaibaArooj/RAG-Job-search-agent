import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class RAGPipeline:
    """
    RAG Pipeline using Google Gemini (free tier).
    Takes top ranked jobs + user query, builds a prompt,
    sends it to Gemini, and returns AI recommendations.
    """

    def __init__(self):
        self.model = genai.GenerativeModel("gemini-3.6-flash")
        self.top_k = 5
        print("RAGPipeline ready (Gemini).")

    def build_prompt(self, query, jobs):
        job_context = ""
        for i, job in enumerate(jobs[:self.top_k], 1):
            job_context += f"""
Job {i}:
- Title: {job['title']}
- Company: {job['company']}
- Location: {job['location']}
- Source: {job['source']}
- Description: {job['description'][:300]}...
"""

        prompt = f"""You are a helpful job search assistant.

A user is searching for: "{query}"

Here are the top {min(self.top_k, len(jobs))} most relevant job listings:

{job_context}

Based on the user's search, pick the TOP 3 most suitable jobs.
For each, write ONE clear sentence explaining why it matches.

Format exactly like this:
1. [Job Title] at [Company] - [One sentence explanation]
2. [Job Title] at [Company] - [One sentence explanation]
3. [Job Title] at [Company] - [One sentence explanation]"""

        return prompt

    def run(self, query, jobs):
        if not jobs:
            return None
        try:
            prompt = self.build_prompt(query, jobs)
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"RAG Pipeline error: {e}")
            return None