import time
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from github_predictor.utils.config import setup_logger

logger = setup_logger("trending_scraper")


class TrendingScraper:
    BASE_URL = "https://github.com/trending"

    def get_trending_repos(
        self, language: str = "", since: str = "daily"
    ) -> List[Dict]:
        """
        Gets current trending repositories

        Args:
            language: Programming language
            since: Time range - "daily", "weekly", or "monthly" (default: "daily")

        Returns:
            List of repository dictionaries with keys: author, name, url, description, etc.
        """
        # Build URL with query parameters
        url = self.BASE_URL
        params = {"since": since}

        if language and language.lower() != "all":
            url = f"{self.BASE_URL}/{language.lower()}"

        try:
            logger.info(
                f"Getting trending repos: language={language or 'all'}, since={since}"
            )
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                repos = self._parse_trending_page(response.text)
                logger.info(f"Successfully fetched {len(repos)} trending repos")
                return repos
            else:
                logger.error(f"Failed to fetch trending repos: {response.status_code}")
                return []

        except requests.exceptions.Timeout:
            logger.error("Request timeout while fetching trending repos")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while fetching trending repos: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error while fetching trending repos: {e}")
            return []

    def _parse_trending_page(self, html: str) -> List[Dict]:
        """
        Parse GitHub trending page HTML to extract repository information.

        Args:
            html: HTML content from GitHub trending page

        Returns:
            List of repository dictionaries
        """
        soup = BeautifulSoup(html, "html.parser")
        repos = []

        articles = soup.find_all("article", class_="Box-row")

        for article in articles:
            try:
                repo_data = {}
                # Repo name in the article
                h2 = article.find("h2")
                if h2:
                    repo_link = h2.find("a")
                    if repo_link and repo_link.get("href"):
                        full_name = repo_link.get("href").strip("/")
                        parts = full_name.split("/")
                        if len(parts) >= 2:
                            repo_data["author"] = parts[0]
                            repo_data["name"] = parts[1]
                            repo_data["url"] = f"https://github.com/{full_name}"
                        else:
                            continue
                    else:
                        continue
                else:
                    continue

                # Extract description
                description_elem = article.find("p", class_="col-9")
                if description_elem:
                    repo_data["description"] = description_elem.get_text(strip=True)
                else:
                    repo_data["description"] = ""

                # Extract language
                lang_elem = article.find(
                    "span", attrs={"itemprop": "programmingLanguage"}
                )
                if lang_elem:
                    repo_data["language"] = lang_elem.get_text(strip=True)
                else:
                    repo_data["language"] = "Unknown"

                # Extract stars (total)
                star_elem = article.find("svg", class_="octicon-star")
                if star_elem and star_elem.parent:
                    star_text = star_elem.parent.get_text(strip=True)
                    # Remove commas and convert to int
                    repo_data["stars"] = self._parse_number(star_text)
                else:
                    repo_data["stars"] = 0

                # Extract forks
                fork_elem = article.find("svg", class_="octicon-repo-forked")
                if fork_elem and fork_elem.parent:
                    fork_text = fork_elem.parent.get_text(strip=True)
                    repo_data["forks"] = self._parse_number(fork_text)
                else:
                    repo_data["forks"] = 0

                # Extract stars today
                stars_today_elem = article.find(
                    "span", class_="d-inline-block float-sm-right"
                )
                if stars_today_elem:
                    stars_today_text = stars_today_elem.get_text(strip=True)
                    # Text is like "1,234 stars today"
                    repo_data["stars_today"] = self._parse_number(stars_today_text)
                else:
                    repo_data["stars_today"] = 0

                repos.append(repo_data)

            except Exception as e:
                logger.warning(f"Error parsing repository entry: {e}")
                continue

        return repos

    def _parse_number(self, text: str) -> int:
        """
        Parse a number from text, handling commas and 'k' suffix.

        Args:
            text: Text like "1,234" or "12.5k" or "1,234 stars today"

        Returns:
            Integer value
        """
        try:
            # Remove common words
            text = (
                text.lower()
                .replace("stars", "")
                .replace("today", "")
                .replace("forks", "")
                .strip()
            )

            # Handle 'k' suffix (e.g., "12.5k" -> 12500)
            if "k" in text:
                text = text.replace("k", "").strip()
                return int(float(text) * 1000)

            # Remove commas
            text = text.replace(",", "")

            return int(text)
        except (ValueError, AttributeError):
            return 0

    def get_trending_repos_with_retry(
        self, language: str = "", since: str = "daily", max_retries: int = 3
    ) -> List[Dict]:
        """
        Fetches trending repos with exponential backoff retry logic.

        Args:
            language: Programming language filter
            since: Time range
            max_retries: Maximum number of retry attempts

        Returns:
            List of repository dictionaries
        """
        for attempt in range(max_retries):
            repos = self.get_trending_repos(language=language, since=since)

            if repos:
                return repos

            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = 2**attempt
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
                time.sleep(wait_time)

        logger.error(f"Failed to fetch trending repos after {max_retries} attempts")
        return []

    def extract_repo_names(self, repos: List[Dict]) -> List[str]:
        """
        Extract repo names in 'owner/repo' format from repo dictionaries.

        Args:
            repos: List of repository dictionaries with 'author' and 'name' keys

        Returns:
            List of repo names in 'owner/repo' format
        """
        repo_names = []
        for repo in repos:
            author = repo.get("author")
            name = repo.get("name")

            if author and name:
                repo_name = f"{author}/{name}"
                repo_names.append(repo_name)

        return repo_names


if __name__ == "__main__":
    scraper = TrendingScraper()

    # Test fetching trending repos
    repos = scraper.get_trending_repos_with_retry()

    if repos:
        print(f"\nFetched {len(repos)} trending repositories:\n")

        repo_names = []
        for repo in repos:
            author = repo.get("author")
            name = repo.get("name")

            if author and name:
                repo_name = f"{author}/{name}"
                repo_names.append(repo_name)

        for i, repo_name in enumerate(repo_names[:10], 1):
            print(f"{i}. {repo_name}")

        # Show sample data
        if repos:
            print(f"\nSample repo data:")
            sample = repos[0]
            print(f"  Name: {sample.get('author')}/{sample.get('name')}")
            print(f"  Description: {sample.get('description', 'N/A')[:80]}...")
            print(f"  Language: {sample.get('language')}")
            print(f"  Stars: {sample.get('stars')}")
            print(f"  Stars today: {sample.get('stars_today')}")
    else:
        print("Failed to fetch trending repositories")
