from datetime import datetime, timedelta

import pandas as pd

from github_predictor.pipelines.feature_pipeline.feature_enricher import FeatureEnricher
from github_predictor.pipelines.hopsworks_client import HopsworksClient
from github_predictor.pipelines.feature_pipeline.trending_labeler import TrendingLabeler
from github_predictor.pipelines.feature_pipeline.trending_scraper import TrendingScraper
from github_predictor.utils.config import DATA_DIR, setup_logger

logger = setup_logger("daily_pipeline")


def run_daily_features():
    """
    Process:
    1. Fetch today's trending repos
    2. Store trending list in history
    3. Enrich with features (save unlabeled to CSV)
    4. Check for data from 7 days ago
    5. If exists: label it and upload to Hopsworks, delete unlabeled file
    """
    logger.info("Starting daily feature pipeline")

    trending_scraper = TrendingScraper()
    enricher = FeatureEnricher()
    labeler = TrendingLabeler()

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    logger.info(f"Processing date: {today_str}")

    # 1. Fetch today's trending repos
    logger.info("Getting today's repositories")
    repos = trending_scraper.get_trending_repos_with_retry()

    if not repos:
        logger.error("Failed to fetch trending repos")
        return

    # Extract repo names
    repo_names = trending_scraper.extract_repo_names(repos)
    logger.info(f"Found {len(repo_names)} trending repos")

    # 2. Store trending list in history
    labeler.history.add_trending_list(today_str, repo_names)

    # 3. Enrich today's repos
    logger.info("Enriching features for today's repositories")
    features_df = enricher.enrich_batch(
        repo_names,
        today,
        max_workers=5,
        # I think it is better if we skip HN for the backfill
        skip_hn=True,
    )

    if features_df.empty:
        logger.error("Failed to enrich any repos")
        return

    features_df["collection_date"] = today_str

    # Add a placeholder for the label, as we don't know it yet.
    # This makes the data available for inference.
    features_df["is_trending"] = -1 
    
    # Upload today's features for inference
    logger.info("Uploading today's unlabeled features for inference.")
    hops_client = HopsworksClient()
    hops_client.connect()
    hops_client.insert_features(features_df, wait_for_job=True)
    logger.info("Successfully uploaded today's features for inference.")

    # Save unlabeled data for labeling after 7 days
    unlabeled_path = DATA_DIR / f"unlabeled_{today_str}.csv"
    features_df.to_csv(unlabeled_path, index=False)
    logger.info(f"Saved {len(features_df)} unlabeled features to {unlabeled_path} for future labeling.")

    # 4. Check for data from 7 days ago to label
    seven_days_ago = today - timedelta(days=7)
    seven_days_ago_str = seven_days_ago.strftime("%Y-%m-%d")
    unlabeled_file = DATA_DIR / f"unlabeled_{seven_days_ago_str}.csv"

    # Check if we have a file and 7 days have passed
    if unlabeled_file.exists():
        logger.info(f"Found unlabeled data from {seven_days_ago_str}")

        # 5. Label data from 7 days ago
        logger.info("Loading unlabeled features")
        old_df = pd.read_csv(unlabeled_file)

        logger.info("Creating labels with 7-day lookback")
        labeled_df = labeler.create_labels(old_df, lookback_days=7)

        # Upload to Hopsworks
        logger.info("Connecting to Hopsworks")
        hops_client = HopsworksClient()
        hops_client.connect()
        hops_client.get_or_create_feature_group()

        logger.info(f"Uploading {len(labeled_df)} labeled features to Hopsworks...")
        hops_client.insert_features(labeled_df, wait_for_job=True)

        # Delete unlabeled file
        unlabeled_file.unlink()
        logger.info(f"Deleted unlabeled file: {unlabeled_file}")

        # Summary statistics
        logger.info("\n" + "=" * 60)
        logger.info("DAILY PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Today's date: {today_str}")
        logger.info(f"Repos collected today: {len(features_df)}")
        logger.info(f"Labeled date: {seven_days_ago_str}")
        logger.info(f"Features uploaded: {len(labeled_df)}")
        logger.info(f"Trending (1): {(labeled_df['is_trending'] == 1).sum()}")
        logger.info(f"Not trending (0): {(labeled_df['is_trending'] == 0).sum()}")
        logger.info("=" * 60)

    else:
        logger.info(
            f"No unlabeled data found for {seven_days_ago_str}. "
            f"Data will be labeled on {(today + timedelta(days=7)).strftime('%Y-%m-%d')}"
        )
        logger.info("\n" + "=" * 60)
        logger.info("DAILY PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Today's date: {today_str}")
        logger.info(f"Repos collected: {len(features_df)}")
        logger.info(f"Saved as unlabeled (will label in 7 days)")
        logger.info("=" * 60)

    logger.info("Daily pipeline complete!")


if __name__ == "__main__":
    run_daily_features()
