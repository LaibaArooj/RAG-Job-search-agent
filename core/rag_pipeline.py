import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Single point of change for the LLM.
#
# The SRS names Llama 3 8B-instant. Groq has since decommissioned its Llama 3
# chat models: `llama3-8b-8192` returns "has been decommissioned" and
# `llama-3.1-8b-instant` returns 404. No Llama chat model remains on the Groq
# model list, so this is a forced substitution, not a preference. Provider,
# cost and the free-tier constraint are all unchanged. Needs supervisor
# sign-off and a line in docs/PROJECT_SPEC.md § Deviations.
GROQ_MODEL = "groq/compound-mini"


class RAGPipeline:
    """Builds a prompt from the top ranked jobs and asks Groq to explain three picks."""

    def __init__(self, model=GROQ_MODEL, top_k=5):
        """Create a Groq client; the API key comes from the environment, never hardcoded."""
        self.model = model
        self.top_k = top_k
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def build_prompt(self, query, jobs):
        """Format the top k already-ranked jobs into a single prompt string."""
        lines = []
        for i, job in enumerate(jobs[:self.top_k], 1):
            lines.append(
                f"Job {i}:\n"
                f"- Title: {job.get('title', 'Unknown')}\n"
                f"- Company: {job.get('company', 'Unknown')}\n"
                f"- Location: {job.get('location', 'Unknown')}\n"
                f"- Source: {job.get('source', 'Unknown')}\n"
                f"- Description: {str(job.get('description', ''))[:400]}\n"
            )
        job_context = "\n".join(lines)

        return (
            f'A job seeker searched for: "{query}"\n\n'
            f"These are the highest ranked results already retrieved and re-ranked "
            f"for that search:\n\n{job_context}\n"
            f"Recommend the three best matches from the list above. For each one give "
            f"the job title, the company, and two sentences explaining why it fits the "
            f"search. Only use jobs from the list. Do not invent jobs. "
            f"Write plain text, no markdown."
        )

    def fallback(self):
        """Return None so the caller hides the AI section and still shows ranked results (FR-018)."""
        return None

    def run(self, query, jobs):
        """Generate recommendations for the top ranked jobs, or fall back if Groq is unavailable."""
        if not jobs:
            return self.fallback()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": self.build_prompt(query, jobs)}],
                temperature=0.3,
                max_tokens=700,
            )
            text = (response.choices[0].message.content or "").strip()
            return text or self.fallback()
        except Exception as e:
            print(f"Groq API error: {e}")
            return self.fallback()
