from pathlib import Path
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

MODEL_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "all-MiniLM-L6-v2"
)

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

if not (MODEL_PATH / "modules.json").exists():
    model = SentenceTransformer(MODEL_NAME)
    model.save(str(MODEL_PATH))

print(f"Sentence Transformer model ready at: {MODEL_PATH}")