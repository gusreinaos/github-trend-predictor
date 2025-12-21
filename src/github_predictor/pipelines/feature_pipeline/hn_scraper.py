import requests
import pandas as pd
from typing import List, Dict
from github_predictor.utils.config import setup_logger

logger = setup_logger("hn_scraper")


class HNScraper:
    """Scraper for Hacker News API."""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def get_top_stories(self, limit: int = 100) -> List[int]:
        """Fetches IDs of top stories."""
        response = requests.get(f"{self.BASE_URL}/topstories.json")
        if response.status_code != 200:
            return []
        return response.json()[:limit]

    def get_item(self, item_id: int) -> Dict:
        """Fetches details for a specific item."""
        response = requests.get(f"{self.BASE_URL}/item/{item_id}.json")
        if response.status_code != 200:
            return {}
        return response.json()

    def get_github_mentions(self) -> pd.DataFrame:
        """
        Scans top stories for GitHub links and returns buzz metrics.
        """
        top_ids = self.get_top_stories(200)  # Scan more for better coverage
        mentions = []

        for item_id in top_ids:
            item = self.get_item(item_id)
            url = item.get("url", "")
            if "github.com" in url:
                # Extract repo name from URL: github.com/user/repo
                parts = url.split("github.com/")
                if len(parts) > 1:
                    repo_path = parts[1].split("?")[0].rstrip("/")
                    repo_parts = repo_path.split("/")
                    if len(repo_parts) >= 2:
                        repo_name = f"{repo_parts[0]}/{repo_parts[1]}"
                        mentions.append(
                            {
                                "repo_name": repo_name,
                                "hn_score": item.get("score", 0),
                                "hn_comments": item.get("descendants", 0),
                            }
                        )

        if not mentions:
            return pd.DataFrame(columns=["repo_name", "hn_buzz_score"])

        df = pd.DataFrame(mentions)
        # Simple buzz score calculation
        df["hn_buzz_score"] = df["hn_score"] + (df["hn_comments"] * 2)

        # Aggregate in case the same repo is mentioned multiple times
        return df.groupby("repo_name")["hn_buzz_score"].sum().reset_index()


if __name__ == "__main__":
    scraper = HNScraper()
    df = scraper.get_github_mentions()
    print(df.head())
