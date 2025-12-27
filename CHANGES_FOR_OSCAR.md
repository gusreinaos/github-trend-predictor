# Changelog

## Unreleased

This release focuses on improving the model's accuracy through feature engineering and hyperparameter tuning.

### Features

### Model Improvements

- **Improved Language Encoding:** Replaced `LabelEncoder` with `OneHotEncoder` for the `language` feature. This avoids implying an incorrect ordinal relationship between languages and allows the model to treat them as distinct categories.
- **Hyperparameter Tuning:** Integrated `GridSearchCV` into the training pipeline to automatically search for the best hyperparameters for the XGBoost model, improving its predictive performance.

### Pipeline Fixes

- **Fixed Inference Data Population:** Modified the `daily_pipeline.py` to immediately upload daily enriched features to Hopsworks with a placeholder label. This ensures that the inference pipeline has data for the current day to make predictions.

## Previous Releases

### `7f7e5bf` - Fix Feature View Creation

- Fixed an issue where the feature view was not being created correctly in Hopsworks, ensuring a more robust connection to the feature store.

### `4c84f8d` - Correct Artifact Name in Actions

- Updated the GitHub Actions workflow to use the correct artifact name, ensuring CI/CD pipelines run smoothly.

### `8306438` - Refactor Hopsworks Client

- Moved the `hopsworks_client.py` to the root of the `pipelines` directory to improve project structure and clarity.

### `cc77b9t` - Update Hopsworks Config

- Updated the Hopsworks configuration to match the correct project and version settings.
