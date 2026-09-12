from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

print("Loading model... (first run downloads ~80MB, may take a minute)")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded!\n")

# A user's search query
query = "I want to work from home writing content"

# Some example job titles
jobs = [
    "Remote Copywriter",
    "Senior Java Developer",
    "Content Writer - Work From Anywhere",
    "Warehouse Forklift Operator"
]

# Convert text to vectors (embeddings)
query_vector = model.encode(query)
job_vectors = model.encode(jobs)

print(f"Query: '{query}'\n")
print("Similarity scores (higher = more relevant):\n")

for job, vector in zip(jobs, job_vectors):
    score = cos_sim(query_vector, vector).item()
    print(f"{score:.3f}  -  {job}")