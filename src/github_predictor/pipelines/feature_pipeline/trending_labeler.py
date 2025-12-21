import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set

import pandas as pd

from github_predictor.utils.config import DATA_DIR, setup_logger

logger = setup_logger("trending_labeler")


class TrendingHistory:
    def __init__(self, storage_path: Path = DATA_DIR / "trending_history.json"):
        self.storage_path = storage_path
        self.history = self._load()

    def _load(self) -> dict:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    history = json.load(f)
                logger.info(f"Loaded trending history: {len(history)} days")
                return history
            except json.JSONDecodeError as e:
                logger.error(f"Error loading trending history: {e}")
                return {}
        else:
            logger.info("No existing trending history found, starting fresh")
            return {}

    def _save(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.history, f, indent=2)
            logger.info(f"Saved trending history: {len(self.history)} days")
        except Exception as e:
            logger.error(f"Error saving trending history: {e}")

    def add_trending_list(self, date: str, repo_names: List[str]):
        self.history[date] = repo_names
        self._save()
        logger.info(f"Added {len(repo_names)} trending repos for {date}")

    def get_trending_repos(self, start_date: str, end_date: str) -> Set[str]:
        trending_repos = set()

        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        for date_str, repos in self.history.items():
            try:
                date = datetime.fromisoformat(date_str)
                if start <= date <= end:
                    trending_repos.update(repos)
            except ValueError:
                logger.warning(f"Invalid date format in history: {date_str}")
                continue

        logger.info(
            f"Found {len(trending_repos)} unique repos trending "
            f"between {start_date} and {end_date}"
        )
        return trending_repos

    def is_trending_in_window(
        self, repo_name: str, start_date: str, end_date: str
    ) -> bool:
        trending_repos = self.get_trending_repos(start_date, end_date)
        return repo_name in trending_repos

    def get_date_range(self) -> tuple:
        if not self.history:
            return None, None

        dates = sorted(self.history.keys())
        return dates[0], dates[-1]


class TrendingLabeler:
    def __init__(self, history: TrendingHistory = None):
        self.history = history if history else TrendingHistory()

    def create_labels(
        self, features_df: pd.DataFrame, lookback_days: int = 7
    ) -> pd.DataFrame:
        """
        Create is_trending labels using lookback.

        For each row with collection_date D:
        - Check if repo appears in trending between D+1 and D+lookback_days
        - Set is_trending = 1 if yes, 0 if no

        Args:
            features_df: DataFrame with features and collection_date column
            lookback_days: Number of days to look ahead (default: 7)

        Returns:
            DataFrame with is_trending column added
        """
        if features_df.empty:
            logger.warning("Empty features DataFrame, no labels to create")
            return features_df

        if "collection_date" not in features_df.columns:
            raise ValueError("features_df must have 'collection_date' column")

        if "repo_name" not in features_df.columns:
            raise ValueError("features_df must have 'repo_name' column")

        logger.info(
            f"Creating labels for {len(features_df)} rows with {lookback_days}-day lookback"
        )

        labels = []

        for _, row in features_df.iterrows():
            collection_date = row["collection_date"]
            repo_name = row["repo_name"]

            # Calculate future window: D+1 to D+lookback_days
            collection_dt = datetime.fromisoformat(collection_date)
            start_date = (collection_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = (collection_dt + timedelta(days=lookback_days)).strftime(
                "%Y-%m-%d"
            )

            # Check if repo trended in window
            is_trending = self.history.is_trending_in_window(
                repo_name, start_date, end_date
            )

            labels.append(1 if is_trending else 0)

        # Add labels to DataFrame
        features_df = features_df.copy()
        features_df["is_trending"] = labels

        # Log label distribution
        trending_count = sum(labels)
        not_trending_count = len(labels) - trending_count
        logger.info(
            f"Label distribution: {trending_count} trending (1), "
            f"{not_trending_count} not trending (0)"
        )

        return features_df

    def can_label_date(self, collection_date: str, lookback_days: int = 7) -> bool:
        """
        Check if we have enough trending history to label a specific date.

        Args:
            collection_date: Date string (YYYY-MM-DD)
            lookback_days: Number of days to look ahead

        Returns:
            True if we can label this date, False otherwise
        """
        collection_dt = datetime.fromisoformat(collection_date)
        required_end_date = (collection_dt + timedelta(days=lookback_days)).strftime(
            "%Y-%m-%d"
        )

        _, max_date = self.history.get_date_range()

        if max_date is None:
            logger.warning("No trending history available")
            return False

        can_label = max_date >= required_end_date

        if not can_label:
            logger.info(
                f"Cannot label {collection_date}: need data until {required_end_date}, "
                f"only have until {max_date}"
            )

        return can_label


if __name__ == "__main__":
    # Test trending history
    history = TrendingHistory(storage_path=DATA_DIR / "test_trending_history.json")

    # Add some test data
    history.add_trending_list("2024-12-01", ["microsoft/vscode", "pytorch/pytorch"])
    history.add_trending_list("2024-12-02", ["vercel/next.js", "microsoft/vscode"])
    history.add_trending_list("2024-12-08", ["pytorch/pytorch", "openai/gpt-4"])

    # Test querying
    trending = history.get_trending_repos("2024-12-01", "2024-12-05")
    print(f"\nTrending repos (Dec 1-5): {trending}")

    # Test is_trending_in_window
    print(
        f"\nmicrosoft/vscode trending Dec 1-5? {history.is_trending_in_window('microsoft/vscode', '2024-12-01', '2024-12-05')}"
    )
    print(
        f"openai/gpt-4 trending Dec 1-5? {history.is_trending_in_window('openai/gpt-4', '2024-12-01', '2024-12-05')}"
    )

    # Test labeling
    labeler = TrendingLabeler(history)

    test_features = pd.DataFrame(
        [
            {
                "repo_name": "microsoft/vscode",
                "collection_date": "2024-11-30",
                "stars_total": 50000,
            },
            {
                "repo_name": "openai/gpt-4",
                "collection_date": "2024-11-30",
                "stars_total": 30000,
            },
        ]
    )

    labeled_df = labeler.create_labels(test_features)
    print(
        f"\nLabeled features:\n{labeled_df[['repo_name', 'collection_date', 'is_trending']]}"
    )

    # Clean up test file
    (DATA_DIR / "test_trending_history.json").unlink(missing_ok=True)
