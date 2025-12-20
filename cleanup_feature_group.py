#!/usr/bin/env python3
"""Delete the feature group to recreate it with correct schema"""
from src.github_predictor.pipelines.feature_pipeline.hopsworks_client import (
    HopsworksClient,
)

print("Connecting to Hopsworks...")
client = HopsworksClient()
client.connect()

print("Deleting old feature group...")
try:
    fg = client.feature_store.get_feature_group(name="github_trending", version=1)
    fg.delete()
    print("✅ Feature group deleted successfully")
except Exception as e:
    print(f"Note: {e}")
    print("(This is OK if the feature group doesn't exist yet)")

print("\nDone! You can now create a new feature group with the correct schema.")
