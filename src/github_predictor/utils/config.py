import logging
import os
from pathlib import Path

from dotenv import load_dotenv


def setup_logger(name: str = "github_predictor"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def load_env_vars():
    load_dotenv()

    HOPSWORKS_API_KEY = os.getenv("HOPSWORKS_API_KEY")
    if not HOPSWORKS_API_KEY or HOPSWORKS_API_KEY.startswith("your_"):
        logging.warning("HOPSWORKS_API_KEY not found in environment variables.")
        HOPSWORKS_API_KEY = None

    github_token = os.getenv("GITHUB_TOKEN")
    # Ignore placeholder values
    if github_token and github_token.startswith("your_"):
        github_token = None

    return {
        "HOPSWORKS_API_KEY": HOPSWORKS_API_KEY,
        "GITHUB_TOKEN": github_token,
    }


def get_hopsworks_config():
    return {
        "project_name": os.getenv("HOPS_PROJECT_NAME", "id2223scalableml"),
        "feature_group_name": "github_trending",
        "feature_group_version": 1,
        "feature_view_name": os.getenv(
            "HOPS_FEATURE_VIEW_NAME", "github_trending_view"
        ),
        "feature_view_version": int(os.getenv("HOPS_FEATURE_VIEW_VERSION", 1)),
    }


def get_gh_archive_sampling_config():
    """
    Returns GitHub Archive sampling configuration.

    You can customize the sampling strategy to balance speed vs accuracy:
    - specific_hours: List of hours to sample (e.g., [12, 23] for noon and evening)
    - sample_hours: Number of evenly distributed hours to sample
    - None: Fetch all 24 hours (slowest, most accurate)
    """
    # Option 1: Specific hours
    specific_hours_str = os.getenv("GH_ARCHIVE_SPECIFIC_HOURS", "12,23")
    if specific_hours_str:
        return {
            "specific_hours": [int(h) for h in specific_hours_str.split(",")],
            "sample_hours": None,
        }

    # Option 2: Even sampling
    sample_hours = os.getenv("GH_ARCHIVE_SAMPLE_HOURS", None)
    if sample_hours:
        return {
            "specific_hours": None,
            "sample_hours": int(sample_hours),
        }

    # Option 3: Default to [12, 23]
    return {
        "specific_hours": [12, 23],
        "sample_hours": None,
    }


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
