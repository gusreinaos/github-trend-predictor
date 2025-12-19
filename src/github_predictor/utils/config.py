import os
import logging
from pathlib import Path
from dotenv import load_dotenv

def setup_logger(name: str = "github_predictor"):
    """Configures and returns a logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def load_env_vars():
    """Loads environment variables from .env file."""
    load_dotenv()
    
    hops_key = os.getenv("HOPS_KEY")
    if not hops_key:
        logging.warning("HOPS_KEY not found in environment variables.")
    
    return {
        "HOPS_KEY": hops_key,
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
    }

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
