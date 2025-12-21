import time
from datetime import datetime, timedelta

import pandas as pd

from github_predictor.pipelines.feature_pipeline.feature_enricher import FeatureEnricher
from github_predictor.pipelines.feature_pipeline.hopsworks_client import HopsworksClient
from github_predictor.pipelines.feature_pipeline.trending_labeler import TrendingLabeler
from github_predictor.utils.config import setup_logger

logger = setup_logger("backfill_pipeline")


def run_backfill(days: int = 30, top_n_repos: int = 50):
    """
    Backfill pipeline for historical trending data using GH Archive.

    Process:
    1. For each day in range [today - days, today - 7]:
       - Fetch GH Archive data for that day
       - Select top N repos by star_velocity (these are "trending")
       - Store trending list in history
       - Enrich repos with features
       - Store unlabeled features
    2. Label all features using 7-day lookback
    3. Upload to Hopsworks in batches

    Args:
        days: Number of days to backfill (default: 30)
        top_n_repos: Number of top repos by star velocity to consider "trending" (default: 50)
    """

    logger.info(f"Starting GH Archive backfill pipeline for {days} days")
    logger.info(f"Using top {top_n_repos} repos by star velocity as 'trending'")

    enricher = FeatureEnricher()
    labeler = TrendingLabeler()
    hops_client = HopsworksClient()

    end_date = datetime.now() - timedelta(days=7)
    start_date = end_date - timedelta(days=days)

    logger.info(f"Backfill date range: {start_date.date()} to {end_date.date()}")

    all_features = []
    total_repos = 0
    failed_days = 0

    for day_offset in range(days + 1):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        logger.info(f"\nProcessing {date_str} ({day_offset + 1}/{days + 1})")

        try:
            logger.info(f"Fetching GH Archive data for {date_str}...")

            archive_df = enricher.gh_archive.get_velocity_features_for_date(
                current_date,
                specific_hours=[12, 23],
            )

            if archive_df.empty:
                logger.warning(f"No GH Archive data for {date_str}")
                failed_days += 1
                continue

            # Get top N repos by star velocity --> trending
            trending_df = archive_df.nlargest(top_n_repos, "star_velocity")
            repo_names = trending_df["repo_name"].tolist()

            logger.info(
                f"Found {len(repo_names)} trending repos for {date_str} (top by star velocity)"
            )

            # Store trending list
            labeler.history.add_trending_list(date_str, repo_names)
            total_repos += len(repo_names)

            # Enrich features (skip GH Archive since we already have it)
            logger.info(f"Enriching {len(repo_names)} repos")

            # Cache the GH Archive data we just fetched
            enricher._gh_archive_cache = archive_df
            enricher._gh_archive_cache_date = current_date

            features_df = enricher.enrich_batch(
                repo_names,
                current_date,
                max_workers=5,
                skip_gh_archive=False,
                skip_hn=True,  # Skip HN for speed (hn_buzz_score will be 0.0)
            )

            if not features_df.empty:
                features_df["collection_date"] = date_str
                all_features.append(features_df)
                logger.info(f"Enriched {len(features_df)} repos for {date_str}")
            else:
                logger.warning(f"No features collected for {date_str}")

            time.sleep(2)

        except Exception as e:
            logger.error(f"Error processing {date_str}: {e}")
            failed_days += 1
            continue

    # Combine all features
    if not all_features:
        logger.error("No features collected during backfill")
        return

    logger.info(f"Combining features from {len(all_features)} days")
    combined_df = pd.concat(all_features, ignore_index=True)

    logger.info(f"Total features before labeling: {len(combined_df)}")

    # Label features using 7-day lookback
    logger.info("Creating labels with 7-day lookback")
    labeled_df = labeler.create_labels(combined_df, lookback_days=7)

    logger.info(f"Total labeled features: {len(labeled_df)}")

    # Connect to Hopsworks and upload
    logger.info("Connecting to Hopsworks")
    hops_client.connect()
    hops_client.get_or_create_feature_group()

    logger.info("Uploading features to Hopsworks")
    hops_client.insert_features(labeled_df, wait_for_job=True)

    # Summary statistics
    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Days processed: {days + 1 - failed_days}/{days + 1}")
    logger.info(f"Failed days: {failed_days}")
    logger.info(f"Total repos collected: {total_repos}")
    logger.info(f"Total features uploaded: {len(labeled_df)}")
    logger.info(f"Trending (1): {(labeled_df['is_trending'] == 1).sum()}")
    logger.info(f"Not trending (0): {(labeled_df['is_trending'] == 0).sum()}")
    logger.info("=" * 60)

    logger.info("Backfill pipeline complete!")


if __name__ == "__main__":
    import sys

    # Allow custom days and top_n_repos parameters
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    top_n_repos = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    logger.info(f"Running backfill with days={days}, top_n_repos={top_n_repos}")

    run_backfill(days=days, top_n_repos=top_n_repos)
