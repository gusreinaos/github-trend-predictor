"""
A training pipeline that does the following:
1. Connects to Hopsworks.
2. Creates a feature view if it doesn't exist.
3. Reads training data.
4. Trains an XGBoost model.
5. Evaluates the model.
6. Uploads the model to the Hopsworks Model Registry.
"""

import os
import joblib
import pandas as pd
from datetime import datetime

from github_predictor.pipelines.hopsworks_client import HopsworksClient
from github_predictor.utils.config import (
    load_env_vars,
    PROJECT_ROOT,
)


def run_predict():
    """Main function to run the inference pipeline."""

    # Load environment variables
    load_env_vars()

    # Connect to Hopsworks
    hops_client = HopsworksClient()
    hops_client.connect()

    # Get the latest model
    model_name = "github_trending_predictor"
    try:
        model_registry = hops_client.model_registry
        models = model_registry.get_models(name=model_name)
        latest_model = max(models, key=lambda m: m.version)
        print(f"Using model version: {latest_model.version}")
    except:
        print("No models found. Please run the training pipeline first.")
        return

    # Download model artifacts
    model_dir = latest_model.download()
    model = joblib.load(os.path.join(model_dir, "model.pkl"))
    ohe = joblib.load(
        os.path.join(model_dir, "language_encoder.pkl")
    )  # ohe instead of le

    # Get data for inference (today's data)
    # Query feature group directly to get latest data without feature view sync delay
    hops_client.get_or_create_feature_group()

    # Read all data and filter for today's collection_date
    today_str = datetime.now().strftime("%Y-%m-%d")
    all_data = hops_client.feature_group.read()

    # Filter for today's data (unlabeled rows have is_trending = -1)
    data = all_data[all_data["collection_date"].dt.strftime("%Y-%m-%d") == today_str]

    if data.empty:
        print("No new data found for inference.")
        return

    # Prepare data
    inference_data = data.copy()

    # Store repo_name for the final output
    repo_names = inference_data["repo_name"]

    # Preprocessing
    X = inference_data.drop(
        ["repo_name", "collection_date", "hn_buzz_score", "is_trending", "created_at"],
        axis=1,
        errors="ignore",
    )

    # Encode 'language' using OneHotEncoder
    language_encoded = ohe.transform(X[["language"]])
    language_df = pd.DataFrame(
        language_encoded, columns=ohe.get_feature_names_out(["language"]), index=X.index
    )
    X = pd.concat([X.drop("language", axis=1), language_df], axis=1)

    # Predict probabilities
    predictions = model.predict_proba(X)[:, 1]

    # Create output DataFrame
    results = pd.DataFrame(
        {
            "repo_name": repo_names,
            "language": data["language"],  # Keep original language for output
            "probability": predictions,
        }
    )

    # Sort by probability and get top 50
    results = results.sort_values(by="probability", ascending=False).head(50)

    # Save predictions with date at top level
    predictions_path = PROJECT_ROOT / "predictions.json"
    output = {
        "prediction_date": today_str,
        "predictions": results.to_dict(orient="records"),
    }
    import json

    with open(predictions_path, "w") as f:
        json.dump(output, f, indent=4)

    print(f"Top 50 predictions saved to {predictions_path}")


if __name__ == "__main__":
    run_predict()
