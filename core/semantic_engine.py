from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

# Named in the SRS. Single point of change if the asymmetric-search swap to
# msmarco-MiniLM-L6-v3 is approved (see docs/PROJECT_SPEC.md § Deviations).
MODEL_NAME = 'all-MiniLM-L6-v2'


class SemanticEngine:
    """
    Wraps the sentence-transformers model.
    Converts text to embedding vectors and compares them for similarity.
    """

    def __init__(self, model_name=MODEL_NAME):
        """Load the model from the local cache, downloading it only on first run."""
        print("Loading SemanticEngine model...")
        try:
            # Cached weights are ~88 MB on disk. Loading them without contacting the
            # Hugging Face Hub keeps startup independent of the network, so a dropped
            # connection or an unauthenticated rate limit cannot stop the app booting.
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            print("Model not in local cache — downloading once from Hugging Face...")
            self.model = SentenceTransformer(model_name)
        self.embedding_dim = 384
        print("SemanticEngine ready.")

    def encode(self, text):
        """Convert a single string into a 384-dimension vector."""
        return self.model.encode(text)

    def batch_encode(self, texts):
        """Convert a list of strings into a list of vectors (faster than one-by-one)."""
        return self.model.encode(texts)

    def similarity(self, vec1, vec2):
        """Return cosine similarity between two vectors (-1 to 1; near 0 for unrelated text)."""
        return cos_sim(vec1, vec2).item()