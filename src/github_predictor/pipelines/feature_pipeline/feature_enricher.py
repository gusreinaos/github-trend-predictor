from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from github_predictor.pipelines.feature_pipeline.gh_archive_scraper import (
    GHArchiveScraper,
)
from github_predictor.pipelines.feature_pipeline.github_api_client import (
    GitHubAPIClient,
)
from github_predictor.pipelines.feature_pipeline.hn_scraper import HNScraper
from github_predictor.utils.config import setup_logger

logger = setup_logger("feature_enricher")


class FeatureEnricher:
    def __init__(self):
        self.github_client = GitHubAPIClient()
        self.gh_archive = GHArchiveScraper()
        self.hn_scraper = HNScraper()

        self._gh_archive_cache = None
        self._gh_archive_cache_date = None
        self._hn_cache = None

        logger.info("FeatureEnricher initialized with all scrapers")

    def enrich_repo(self, repo_name: str, date: datetime) -> Optional[Dict]:
        result = {
            "repo_name": repo_name,
            "collection_date": date.strftime("%Y-%m-%d"),
            "stars_total": 0,
            "forks_total": 0,
            "star_velocity": 0,
            "commit_frequency": 0,
            "hn_buzz_score": 0.0,  # Always 0.0, both pipelines use skip_hn=True
            "language": "Unknown",
            "days_old": 0,
            "fork_rate": 0.0,
            "popularity_score": 0.0,
            "stars_per_day": 0.0, # Added stars_per_day
        }

        # 1. GitHub API
        try:
            gh_data = self.github_client.get_repo_details(repo_name)
            if not gh_data or not gh_data.get("repo_name"):
                logger.warning(
                    f"GitHub API failed for {repo_name}, using defaults. "
                    f"Repo will have minimal features but won't be lost."
                )
                # Don't return None, continue with defaults and try other data sources
            else:
                result.update(
                    {
                        "stars_total": gh_data.get("stars_total", 0),
                        "forks_total": gh_data.get("forks_total", 0),
                        "language": gh_data.get("language") or "Unknown",
                        "created_at": gh_data.get("created_at"),
                    }
                )

        except Exception as e:
            logger.error(
                f"Error fetching GitHub data for {repo_name}: {e}. "
                f"Continuing with defaults."
            )
            # Don't return None, continue with defaults

        # 2. GH Archive (use cache if available)
        try:
            if self._gh_archive_cache is not None:
                archive_data = self._gh_archive_cache
            else:
                # No cache, fetch for this repo only (not optimal)
                archive_data = self.gh_archive.get_velocity_features_for_date(
                    date, specific_hours=[12, 23]
                )

            if not archive_data.empty:
                repo_archive = archive_data[archive_data["repo_name"] == repo_name]

                if not repo_archive.empty:
                    result["star_velocity"] = int(repo_archive.iloc[0]["star_velocity"])
                    result["commit_frequency"] = int(
                        repo_archive.iloc[0]["commit_frequency"]
                    )

        except Exception as e:
            logger.warning(f"GH Archive failed for {repo_name}: {e}")

        # 3. Hacker News (use cache if available)
        try:
            if self._hn_cache is not None:
                hn_data = self._hn_cache
            else:
                # No cache - fetch HN data
                hn_data = self.hn_scraper.get_github_mentions()

            if not hn_data.empty:
                repo_hn = hn_data[hn_data["repo_name"] == repo_name]

                if not repo_hn.empty:
                    result["hn_buzz_score"] = float(repo_hn.iloc[0]["hn_buzz_score"])

        except Exception as e:
            logger.warning(f"HN scraper failed for {repo_name}: {e}")

        # 4. Compute derived features
        result["days_old"] = self._compute_days_old(result.get("created_at"), date)
        result["fork_rate"] = result["forks_total"] / max(result["stars_total"], 1)
        result["popularity_score"] = (
            result["star_velocity"] * 0.5
            + result["stars_total"] * 0.3
            + result["forks_total"] * 0.2
        )
        result["stars_per_day"] = result["stars_total"] / max(result["days_old"], 1)

        return result

    def _compute_days_old(
        self, created_at: Optional[str], current_date: datetime
    ) -> int:
        """
        Compute repository age in days.

        Args:
            created_at: ISO format timestamp string
            current_date: Current date

        Returns:
            Number of days since creation, or 0 if created_at is invalid
        """
        if not created_at:
            return 0

        try:
            # Parse ISO timestamp (e.g., "2020-01-15T10:30:00Z")
            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

            # Make current_date timezone-aware if it isn't
            if current_date.tzinfo is None:
                # Assume UTC if no timezone
                from datetime import timezone

                current_date = current_date.replace(tzinfo=timezone.utc)

            days = (current_date - created_date).days
            return max(days, 0)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid created_at timestamp: {created_at}, error: {e}")
            return 0

    def enrich_batch(
        self,
        repo_names: List[str],
        date: datetime,
        max_workers: int = 5,
        skip_gh_archive: bool = False,
        skip_hn: bool = False,
    ) -> pd.DataFrame:
        """
        Enrich multiple repositories with parallel API calls.

        Args:
            repo_names: List of repository names
            date: Date for feature collection
            max_workers: Maximum number of parallel workers
            skip_gh_archive: Skip GH Archive data (faster for testing)
            skip_hn: Skip Hacker News data (faster for testing)

        Returns:
            DataFrame with all features
        """
        logger.info(f"Enriching {len(repo_names)} repos with {max_workers} workers")

        # Fetch GH Archive and HN data ONCE for all repos
        if not skip_gh_archive:
            logger.info("Fetching GH Archive data (once for all repos)")
            logger.info("Sampling hours 12 and 23 (extrapolated to 24h)")

            try:
                self._gh_archive_cache = self.gh_archive.get_velocity_features_for_date(
                    date,
                    specific_hours=[12, 23],
                )
                self._gh_archive_cache_date = date
                logger.info(
                    f"Cached GH Archive data: {len(self._gh_archive_cache)} repos with activity"
                )
            except Exception as e:
                logger.warning(f"Failed to fetch GH Archive data: {e}")
                self._gh_archive_cache = pd.DataFrame()
        else:
            logger.info(
                "Skipping GH Archive data (star_velocity and commit_frequency will be 0)"
            )
            self._gh_archive_cache = pd.DataFrame()

        if not skip_hn:
            logger.info("Fetching Hacker News data (once for all repos)...")
            try:
                self._hn_cache = self.hn_scraper.get_github_mentions()
                logger.info(f"Cached HN data: {len(self._hn_cache)} repos mentioned")
            except Exception as e:
                logger.warning(f"Failed to fetch HN data: {e}")
                self._hn_cache = pd.DataFrame()
        else:
            logger.info("Skipping Hacker News data (hn_buzz_score will be 0)")
            self._hn_cache = pd.DataFrame()

        # Now enrich each repo using cached data
        results = []
        failed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(self.enrich_repo, repo, date): repo
                for repo in repo_names
            }

            # Collect results as they complete
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    result = future.result(timeout=60)
                    if result:
                        results.append(result)
                    else:
                        failed_count += 1
                        logger.warning(f"Skipping {repo} - enrichment returned None")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to enrich {repo}: {e}")

        logger.info(
            f"Enrichment complete: {len(results)} successful, {failed_count} failed"
        )

        # Clear cache after batch completes
        self._gh_archive_cache = None
        self._gh_archive_cache_date = None
        self._hn_cache = None

        return pd.DataFrame(results)


if __name__ == "__main__":
    # Test feature enricher with a few repos
    print("=" * 60)
    print("FEATURE ENRICHER TEST")
    print("=" * 60)
    print("\nTesting with 3 repos...")
    print("FAST MODE: Skipping GH Archive and HN (takes too long for testing)")
    print("For full data, use the backfill or daily pipelines\n")

    enricher = FeatureEnricher()

    test_repos = [
        "microsoft/vscode",
        "pytorch/pytorch",
        "vercel/next.js",
    ]

    date = datetime.now()

    # Skip slow data sources for quick testing
    features_df = enricher.enrich_batch(
        test_repos,
        date,
        max_workers=3,
        skip_gh_archive=True,  # Skip 2-5GB download
        skip_hn=True,  # Skip HN scraping
    )

    if not features_df.empty:
        print(f"\nSuccessfully enriched {len(features_df)} repositories:\n")
        print(
            features_df[
                [
                    "repo_name",
                    "stars_total",
                    "forks_total",
                    "language",
                    "days_old",
                    "fork_rate",
                ]
            ]
        )
        print(f"\nSample repo details:")
        sample = features_df.iloc[0]
        print(f"  Name: {sample['repo_name']}")
        print(f"  Stars: {sample['stars_total']:,}")
        print(f"  Forks: {sample['forks_total']:,}")
        print(f"  Language: {sample['language']}")
        print(f"  Age: {sample['days_old']} days")
        print(f"  Fork rate: {sample['fork_rate']:.2%}")
    else:
        print("❌ Failed to enrich any repositories")
