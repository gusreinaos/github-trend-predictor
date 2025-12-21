from typing import Optional

import pandas as pd

from github_predictor.utils.config import (
    get_hopsworks_config,
    load_env_vars,
    setup_logger,
)

logger = setup_logger("hopsworks_client")


class HopsworksClient:
    def __init__(self):
        env = load_env_vars()
        self.api_key = env.get("HOPS_KEY")

        if not self.api_key:
            raise ValueError(
                "HOPS_KEY environment variable is required. "
                "Please set it in your .env file."
            )

        self.project = None
        self.feature_store = None
        self.feature_group = None

        logger.info("HopsworksClient initialized")

    def connect(self, project_name: Optional[str] = None):
        try:
            import hopsworks

            config = get_hopsworks_config()
            project_name = project_name or config["project_name"]

            logger.info(f"Connecting to Hopsworks project: {project_name}")

            self.project = hopsworks.login(
                api_key_value=self.api_key, project=project_name
            )

            self.feature_store = self.project.get_feature_store()

            logger.info("Successfully connected to Hopsworks")

        except Exception as e:
            logger.error(f"Failed to connect to Hopsworks: {e}")
            raise

    def get_or_create_feature_group(
        self,
        name: Optional[str] = None,
        version: Optional[int] = None,
        description: str = "GitHub trending repository features with 7-day labels",
    ):
        if not self.feature_store:
            raise RuntimeError("Not connected to Hopsworks. Call connect() first.")

        config = get_hopsworks_config()
        name = name or config["feature_group_name"]
        version = version or config["feature_group_version"]

        fg_exists = False
        try:
            self.feature_group = self.feature_store.get_feature_group(
                name=name, version=version
            )
            # Sometimes get_feature_group returns an object even if it doesn't exist
            if self.feature_group:
                fg_exists = True
        except Exception:
            fg_exists = False

        if fg_exists:
            logger.info(f"Using existing feature group: {name} v{version}")
        else:
            logger.info(f"Creating new feature group: {name} v{version}")
            self.feature_group = self.feature_store.create_feature_group(
                name=name,
                version=version,
                primary_key=["repo_name", "collection_date"],
                event_time="collection_date",
                description=description,
                online_enabled=False,
            )
            logger.info(f"Created feature group: {name} v{version}")

    def insert_features(self, df: pd.DataFrame, wait_for_job: bool = True):
        if not self.feature_group:
            raise RuntimeError(
                "Feature group not initialized. Call get_or_create_feature_group() first."
            )

        # Validate schema
        required_cols = [
            "repo_name",
            "collection_date",
            "language",
            "stars_total",
            "forks_total",
            "star_velocity",
            "commit_frequency",
            "hn_buzz_score",  # Always 0.0 (skip_hn=True in both pipelines)
            "days_old",
            "fork_rate",
            "popularity_score",
            "is_trending",
        ]

        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Ensure correct types
        df = df.copy()

        # Convert collection_date to datetime (Hopsworks requires TIMESTAMP/DATE for event_time)
        df["collection_date"] = pd.to_datetime(df["collection_date"])

        df = df.astype(
            {
                "repo_name": "string",
                # collection_date is already datetime from above
                "language": "string",
                "stars_total": "int64",
                "forks_total": "int64",
                "star_velocity": "int64",
                "commit_frequency": "int64",
                "hn_buzz_score": "float64",
                "days_old": "int64",
                "fork_rate": "float64",
                "popularity_score": "float64",
                "is_trending": "int64",
            }
        )

        logger.info(f"Inserting {len(df)} rows into feature group")

        try:
            self.feature_group.insert(df, write_options={"wait_for_job": wait_for_job})
            logger.info(f"Successfully inserted {len(df)} rows")

        except Exception as e:
            logger.error(f"Failed to insert features: {e}")
            raise

    def get_features(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retrieve features from feature store.

        Args:
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            DataFrame with features
        """
        if not self.feature_group:
            raise RuntimeError(
                "Feature group not initialized. Call get_or_create_feature_group() first."
            )

        try:
            # Build query
            query = self.feature_group.select_all()

            # Apply date filters if provided
            if start_date and end_date:
                query = query.filter(
                    (self.feature_group.collection_date >= start_date)
                    & (self.feature_group.collection_date <= end_date)
                )
            elif start_date:
                query = query.filter(self.feature_group.collection_date >= start_date)
            elif end_date:
                query = query.filter(self.feature_group.collection_date <= end_date)

            # Execute query
            df = query.read()

            logger.info(f"Retrieved {len(df)} rows from feature store")
            return df

        except Exception as e:
            logger.error(f"Failed to retrieve features: {e}")
            raise

    def get_feature_group_statistics(self) -> dict:
        """
        Get statistics about the feature group.

        Returns:
            Dictionary with statistics
        """
        if not self.feature_group:
            raise RuntimeError(
                "Feature group not initialized. Call get_or_create_feature_group() first."
            )

        try:
            df = self.feature_group.read()

            stats = {
                "total_rows": len(df),
                "unique_repos": df["repo_name"].nunique(),
                "date_range": (
                    df["collection_date"].min(),
                    df["collection_date"].max(),
                ),
                "label_distribution": df["is_trending"].value_counts().to_dict(),
                "languages": df["language"].value_counts().head(10).to_dict(),
            }

            logger.info(f"Feature group statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            raise


if __name__ == "__main__":
    try:
        client = HopsworksClient()
        client.connect()

        try:
            client.get_or_create_feature_group(name="github_trending", version=1)
            print("Feature group created or already exists!")
        except Exception as e:
            print("Failed to create feature group:", e)

        client.get_or_create_feature_group()

        test_data = pd.DataFrame(
            [
                {
                    "repo_name": "test/repo",
                    "collection_date": "2024-12-20",
                    "language": "Python",
                    "stars_total": 1000,
                    "forks_total": 100,
                    "star_velocity": 50,
                    "commit_frequency": 20,
                    "hn_buzz_score": 100.0,
                    "days_old": 365,
                    "fork_rate": 0.1,
                    "popularity_score": 350.0,
                    "is_trending": 1,
                }
            ]
        )

        print("\nTest data:")
        print(test_data)

        # Uncomment to test writing something to Hopsworks
        # client.insert_features(test_data)
        # print("\nSuccessfully inserted test data")

        print("\nHopsworks client test complete!")

    except Exception as e:
        print(f"\nTest failed: {e}")
