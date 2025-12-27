# GitHub Actions Pipeline Documentation

## 🔄 Workflow Pipeline Overview

This project uses three automated GitHub Actions workflows that form a complete ML pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                    WEEKLY (Sunday 02:00 UTC)                │
│                                                             │
│  training-weekly.yml → Train XGBoost Model                  │
│                        Save to Hopsworks Model Registry     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    DAILY (06:11 UTC)                        │
│                                                             │
│  repos-daily.yml → Fetch GitHub Trending Data               │
│                    Enrich Features                          │
│                    Save to Hopsworks Feature Store          │
│                         ↓                                   │
│                    (triggers)                               │
│                         ↓                                   │
│  inference-daily.yml → Load Latest Model                    │
│                        Generate Predictions                 │
│                        Upload Results                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Workflow Details

### 1. `training-weekly.yml` - Model Training

**Schedule**: Every Sunday at 02:00 UTC  
**Command**: `uv run train`  
**Purpose**: Retrain the XGBoost classifier with accumulated data

**Steps**:

1. Checkout repository
2. Setup Python 3.10
3. Install dependencies with UV
4. Run training pipeline
5. Upload model artifacts (metrics, plots, model files)

**Required Secrets**:

- `HOPSWORKS_API_KEY` - Access to feature store and model registry

**Outputs**:

- Trained model saved to Hopsworks Model Registry
- Training metrics and plots uploaded as artifacts (90-day retention)

---

### 2. `repos-daily.yml` - Feature Pipeline

**Schedule**: Daily at 06:11 UTC  
**Command**: `uv run daily-features`  
**Purpose**: Collect and process daily GitHub trending data

**Steps**:

1. Checkout repository
2. Setup Python 3.10
3. Install dependencies with UV
4. Run daily feature pipeline
5. **Automatically triggers** `inference-daily.yml` on success

**Required Secrets**:

- `HOPSWORKS_API_KEY` - Write to feature store
- `GITHUB_TOKEN` - (Optional) Avoid rate limits

**Outputs**:

- ~100-200 new feature records in Hopsworks
- Triggers inference workflow

---

### 3. `inference-daily.yml` - Inference Pipeline

**Trigger**: Automatically runs after `repos-daily.yml` completes successfully  
**Command**: `uv run predict`  
**Purpose**: Generate daily predictions for trending repositories

**Steps**:

1. Checkout repository
2. Setup Python 3.10
3. Install dependencies with UV
4. Run inference pipeline
5. Upload prediction results

**Required Secrets**:

- `HOPSWORKS_API_KEY` - Load model and features
- `ANTHROPIC_API_KEY` - (Optional) Generate Claude insights

**Outputs**:

- Top 50 predicted trending repos with probabilities
- Predictions uploaded as artifacts (30-day retention)

---

## 🔑 Required GitHub Secrets

Add these secrets in your repository settings (`Settings → Secrets and variables → Actions`):

| Secret Name         | Required       | Purpose                                           |
| ------------------- | -------------- | ------------------------------------------------- |
| `HOPSWORKS_API_KEY` | ✅ Yes         | Access Hopsworks feature store and model registry |
| `GITHUB_TOKEN`      | ⚠️ Recommended | Avoid GitHub API rate limits                      |
| `ANTHROPIC_API_KEY` | 🌟 A-Grade     | Enable Claude-powered insights                    |

---

## 🚀 Manual Triggers

All workflows can be manually triggered via GitHub Actions UI:

1. Go to **Actions** tab in GitHub
2. Select workflow (e.g., `repos-daily`)
3. Click **Run workflow** → **Run workflow**

This is useful for:

- Testing changes
- Recovering from failures
- Running pipelines on-demand

---

## 📊 Workflow Execution Flow

### Normal Daily Flow:

```
06:11 UTC → repos-daily.yml starts
            ↓
            Fetches trending repos
            ↓
            Enriches features
            ↓
            Saves to Hopsworks
            ↓
            ✅ Success
            ↓
            inference-daily.yml starts
            ↓
            Loads latest model
            ↓
            Generates predictions
            ↓
            Uploads results
            ↓
            ✅ Complete
```

### Weekly Training Flow:

```
Sunday 02:00 UTC → training-weekly.yml starts
                   ↓
                   Loads feature data
                   ↓
                   Trains XGBoost model
                   ↓
                   Evaluates performance
                   ↓
                   Saves to Model Registry
                   ↓
                   ✅ New model ready for next inference
```

---

## ⚠️ Important Notes

### Workflow Chaining

- `inference-daily.yml` **only runs** if `repos-daily.yml` succeeds
- If feature pipeline fails, inference is skipped (prevents bad predictions)
- Both can be triggered manually for testing

### Timing Strategy

- Training runs **Sunday 02:00** (before Monday's daily pipeline)
- Daily pipelines run **06:11** (arbitrary time to avoid :00 congestion)
- Inference runs **immediately after** feature pipeline completes

### Data Availability

- Training requires **7+ days** of labeled data (see `FEATURES.md`)
- First week: Only feature collection runs
- Week 2+: Full pipeline with predictions

---

## 🐛 Troubleshooting

### Inference doesn't run after features

**Check**: Did `repos-daily.yml` succeed?  
**Solution**: View workflow logs, fix feature pipeline errors

### Training fails with "insufficient data"

**Check**: Have you collected 7+ days of data?  
**Solution**: Wait for more data or reduce `LOOKBACK_DAYS` in config

### Rate limit errors

**Check**: Is `GITHUB_TOKEN` secret set?  
**Solution**: Add GitHub personal access token to secrets

---

## 📝 Next Steps

1. **Set up secrets** in GitHub repository settings
2. **Run backfill** manually first: `uv run backfill` (locally or via workflow)
3. **Wait 7 days** for label generation
4. **Trigger training** manually to create first model
5. **Enable daily workflows** - they'll run automatically

---

**Last Updated**: 2024-12-21  
**Status**: Production Ready
