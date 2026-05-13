from pathlib import Path

BASE_DIR = Path(__file__).parent

SKILLS_DIR = BASE_DIR / "skills"
DATA_DIR = BASE_DIR / "data"
MEMORY_PATH = DATA_DIR / "memory.json"
SAMPLE_DB_PATH = DATA_DIR / "sample.db"

ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 4
