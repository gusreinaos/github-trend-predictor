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
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV # Added GridSearchCV
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.preprocessing import LabelEncoder, OneHotEncoder # Added OneHotEncoder
import matplotlib.pyplot as plt
import seaborn as sns


from github_predictor.pipelines.hopsworks_client import HopsworksClient
from github_predictor.utils.config import (
    load_env_vars,
    PROJECT_ROOT,
)


def run_train():
    """Main function to run the training pipeline."""

    # Load environment variables
    load_env_vars()

    # Connect to Hopsworks
    hops_client = HopsworksClient()
    hops_client.connect()

    # Get or create feature view
    feature_view = hops_client.get_or_create_feature_view()

    if feature_view is None:
        print("ERROR: Feature view could not be created or retrieved.")
        print("Make sure you have run the feature pipeline first:")
        print("  uv run daily-features  (for daily data)")
        print("  uv run backfill        (for historical data)")
        return

    # Get training data
    X, y = feature_view.training_data(description="GitHub Trending Training Data")

    # Preprocessing
    # Drop unnecessary columns
    X = X.drop(["repo_name", "collection_date", "hn_buzz_score", "created_at"], axis=1)

    # Encode 'language' using OneHotEncoder
    ohe = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    language_encoded = ohe.fit_transform(X[['language']])
    language_df = pd.DataFrame(language_encoded, columns=ohe.get_feature_names_out(['language']), index=X.index)
    X = pd.concat([X.drop('language', axis=1), language_df], axis=1)
    
    # Define a smaller parameter grid for demonstration (adjust as needed)
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [3, 5],
        'learning_rate': [0.1, 0.01]
    }

    # Initialize GridSearchCV
    grid_search = GridSearchCV(
        estimator=xgb.XGBClassifier(objective="binary:logistic", eval_metric="logloss", enable_categorical=False),
        param_grid=param_grid,
        cv=3, # Using 3-fold cross-validation
        scoring='accuracy',
        n_jobs=-1, # Use all available cores
        verbose=1
    )

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Fit GridSearchCV
    grid_search.fit(X_train, y_train)

    # Get the best model
    model = grid_search.best_estimator_
    print(f"\nBest parameters found: {grid_search.best_params_}")
    print(f"Best cross-validation accuracy: {grid_search.best_score_:.4f}")

    # Evaluate model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {accuracy:.4f}")

    # Create confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax)
    plt.title("Confusion Matrix")
    plt.ylabel("Actual")
    plt.xlabel("Predicted")

    # Ensure the directory exists
    metrics_dir = PROJECT_ROOT / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    confusion_matrix_path = metrics_dir / "confusion_matrix.png"
    plt.savefig(confusion_matrix_path)
    print(f"Confusion matrix saved to {confusion_matrix_path}")

    # Print classification report
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Register model in Hopsworks
    hops_client.register_model(
        model,
        ohe, # Passed ohe instead of le
        "github_trending_predictor",
        "Predicts if a GitHub repository will trend.",
        {"accuracy": accuracy},
        X_train,
        y_train,
    )

    print("Model successfully registered in Hopsworks.")


if __name__ == "__main__":
    run_train()
