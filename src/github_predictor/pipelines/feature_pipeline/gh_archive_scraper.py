import requests
import gzip
import json
import io
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
from github_predictor.utils.config import setup_logger, DATA_DIR

logger = setup_logger("gh_archive_scraper")


class GHArchiveScraper:
    """Scraper for GH Archive (gharchive.org)."""

    BASE_URL = "https://data.gharchive.org"

    def fetch_hour_data(self, date_str: str, hour: int) -> List[Dict]:
        """
        Fetches events for a specific hour.
        Format: YYYY-MM-DD-H.json.gz
        """
        url = f"{self.BASE_URL}/{date_str}-{hour}.json.gz"
        logger.info(f"Fetching data from {url}")

        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Failed to fetch data: {response.status_code}")
            return []

        events = []
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
                for line in f:
                    events.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error parsing GZIP data: {e}")
            return []

        return events

    def get_velocity_features(self, hours: int = 24) -> pd.DataFrame:
        """
        Aggregates star velocity and commit frequency for the last N hours.
        """
        now = datetime.utcnow()
        all_events = []

        for i in range(1, hours + 1):
            target_time = now - timedelta(hours=i)
            date_str = target_time.strftime("%Y-%m-%d")
            hour = target_time.hour
            events = self.fetch_hour_data(date_str, hour)
            all_events.extend(events)

        if not all_events:
            return pd.DataFrame()

        df = pd.DataFrame(all_events)

        def extract_repo_name(repo):
            if isinstance(repo, dict):
                return repo.get("name")
            return repo

        # Extract repo name safely
        df["repo_name"] = df["repo"].apply(extract_repo_name)

        # Drop rows where repo_name is None
        df = df.dropna(subset=["repo_name"])

        # Filtering for WatchEvents (Stars) and PushEvents (Commits)
        stars = df[df["type"] == "WatchEvent"]
        commits = df[df["type"] == "PushEvent"]

        # Aggregate by repository name -- based on most stars == higer star velocity
        repo_stars = stars.groupby("repo_name").size().reset_index(name="star_velocity")
        repo_commits = (
            commits.groupby("repo_name").size().reset_index(name="commit_frequency")
        )

        # Merge features
        features = pd.merge(
            repo_stars, repo_commits, on="repo_name", how="outer"
        ).fillna(0)

        return features[["repo_name", "star_velocity", "commit_frequency"]]


if __name__ == "__main__":
    scraper = GHArchiveScraper()
    # Fetching only 1 hour for testing
    df = scraper.get_velocity_features(hours=1)
    if not df.empty:
        print(df.sort_values(by="star_velocity", ascending=False).head(10))
        df.to_csv(DATA_DIR / "gh_archive_test.csv", index=False)
    else:
        print("No data fetched.")
