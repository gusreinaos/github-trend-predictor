import requests
import time
from typing import Dict, Optional
from github_predictor.utils.config import setup_logger, load_env_vars

logger = setup_logger("github_api_client")


class GitHubAPIClient:
    """Client for GitHub REST API."""

    BASE_URL = "https://api.github.com"

    def __init__(self):
        env = load_env_vars()
        self.token = env.get("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        else:
            logger.warning(
                "No GITHUB_TOKEN provided. API rate limits will be severely restricted."
            )

    def get_repo_details(self, repo_full_name: str) -> Dict:
        """Fetches metadata for a repository."""
        url = f"{self.BASE_URL}/repos/{repo_full_name}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            return {
                "repo_name": repo_full_name,
                "stars_total": data.get("stargazers_count", 0),
                "forks_total": data.get("forks_count", 0),
                "language": data.get("language"),
                "description": data.get("description"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            }
        elif response.status_code == 403:
            logger.error("Rate limit exceeded or forbidden.")
            return {}
        else:
            logger.error(
                f"Error fetching repo {repo_full_name}: {response.status_code}"
            )
            return {}


if __name__ == "__main__":
    client = GitHubAPIClient()
    details = client.get_repo_details("psf/requests")
    print(details)
