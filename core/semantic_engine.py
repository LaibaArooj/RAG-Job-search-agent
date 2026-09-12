from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


class SemanticEngine:
    """
    Wraps the sentence-transformers model.
    Converts text to embedding vectors and compares them for similarity.
    """

    def __init__(self):
        print("Loading SemanticEngine model...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dim = 384
        print("SemanticEngine ready.")

    def encode(self, text):
        """Convert a single string into a 384-dimension vector."""
        return self.model.encode(text)

    def batch_encode(self, texts):
        """Convert a list of strings into a list of vectors (faster than one-by-one)."""
        return self.model.encode(texts)

    def similarity(self, vec1, vec2):
        """Return cosine similarity score between two vectors (0 to 1)."""
        return cos_sim(vec1, vec2).item()