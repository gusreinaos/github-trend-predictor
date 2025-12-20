# Feature Documentation

## ⚠️ IMPORTANT: HN Feature Disabled

The `hn_buzz_score` feature has been **disabled** for data consistency. It is kept in the schema for backward compatibility but **should NOT be used in training**.

### Why is HN disabled?

1. **Performance**: HN scraping requires ~200 API calls per day (slow)
2. **Sparsity**: Most GitHub repos are never mentioned on Hacker News
3. **Consistency**: To maintain consistent data between backfill and daily pipelines

Both `backfill_pipeline.py` and `daily_pipeline.py` now use `skip_hn=True`, which means:
- `hn_buzz_score` will always be `0.0` in your training data
- Using this feature would provide no signal to the model

---

## 📊 Features to Use for Training

When building your training pipeline, use these **8 features**:

### Recommended Feature Set:

```python
features = [
    "stars_total",       # Total stars (popularity indicator)
    "forks_total",       # Total forks (developer interest)
    "star_velocity",     # Stars gained in last 24h (momentum indicator)
    "commit_frequency",  # Commits in last 24h (activity indicator)
    "language",          # Programming language (categorical)
    "days_old",          # Repository age in days
    "fork_rate",         # forks / stars ratio (engagement metric)
    "popularity_score",  # Weighted combination of metrics
]

target = "is_trending"  # Binary label (0 or 1)
```

### Features to EXCLUDE:

```python
exclude = [
    "hn_buzz_score",     # ❌ Always 0.0, no signal
    "repo_name",         # ❌ Identifier, not a feature
    "collection_date",   # ❌ Timestamp, not a feature (use as event_time)
]
```

---

## 📐 Feature Descriptions

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `stars_total` | int | 0 - 500k+ | Total stargazers (popularity) |
| `forks_total` | int | 0 - 100k+ | Total forks (developer engagement) |
| `star_velocity` | int | 0 - 10k+ | Stars gained in 24h (extrapolated) |
| `commit_frequency` | int | 0 - 5k+ | Commits in 24h (extrapolated) |
| `language` | string | categorical | Primary programming language |
| `days_old` | int | 0 - 10k+ | Days since repo creation |
| `fork_rate` | float | 0.0 - 1.0+ | Forks per star (engagement ratio) |
| `popularity_score` | float | 0 - 100k+ | 0.5×velocity + 0.3×stars + 0.2×forks |
| `is_trending` | int | 0 or 1 | **TARGET**: Trended in next 7 days? |

---

## ⚙️ Feature Engineering Notes

### `star_velocity` and `commit_frequency`
- Computed from GH Archive data (hourly event logs)
- **Sampled** from hours [12, 23] then **extrapolated** to 24h estimate
- Extrapolation assumes uniform distribution (may overestimate for timezone-heavy repos)

### `popularity_score`
- Weighted combination: `star_velocity × 0.5 + stars_total × 0.3 + forks_total × 0.2`
- This is a **derived feature** - consider whether to include it alongside its components

### `language`
- Categorical feature - will need encoding (e.g., one-hot or label encoding)
- Common values: Python, JavaScript, TypeScript, Go, Rust, Java, etc.
- Some repos have `language = "Unknown"`

### `fork_rate`
- Ratio feature: `forks_total / max(stars_total, 1)`
- Indicates developer engagement vs. casual interest
- High fork_rate (>0.3) suggests active development community

---

## 🎯 Label: `is_trending`

### How Labels are Created:

For a repo collected on date **D**:
- Check if repo appears in trending during **D+1 to D+7**
- Label = `1` if repo trended in that window
- Label = `0` if repo did NOT trend

### Labeling Strategy:
- **7-day lookback** (configurable in `trending_labeler.py`)
- Creates temporal separation between features and labels (prevents data leakage)
- Requires waiting 7 days before a sample can be labeled

---

## ⚠️ Known Data Issues

### 1. Data Source Inconsistency

**Backfill vs Daily pipelines use different trending sources:**

- **Backfill**: Top 50 repos by `star_velocity` from GH Archive (algorithmic)
- **Daily**: Repos from `github.com/trending` (GitHub's curated list)

**Impact**: Initial training data (first few weeks) will be biased toward high-velocity repos.

**Mitigation**: Over time (3+ months), daily data will dominate and reduce bias.

### 2. Sampling Bias in Backfill

Backfill only includes repos that had high `star_velocity` on their collection date. This means:
- Model never sees repos that trended WITHOUT high velocity
- May overweight `star_velocity` feature importance

**For Production**: Consider more diverse sampling strategies.

---

## 💡 Recommendations for Training Pipeline

### 1. Drop HN Feature
```python
# When reading from Hopsworks:
df = hops_client.get_features()
df = df.drop(columns=['hn_buzz_score'])  # Remove unreliable feature
```

### 2. Handle Categorical Features
```python
from sklearn.preprocessing import LabelEncoder

# Encode language
le = LabelEncoder()
df['language_encoded'] = le.fit_transform(df['language'])
```

### 3. Feature Scaling
```python
from sklearn.preprocessing import StandardScaler

# Scale numeric features
numeric_features = ['stars_total', 'forks_total', 'star_velocity',
                   'commit_frequency', 'days_old', 'fork_rate', 'popularity_score']
scaler = StandardScaler()
df[numeric_features] = scaler.fit_transform(df[numeric_features])
```

### 4. Consider Feature Selection
- `popularity_score` is derived from `star_velocity`, `stars_total`, and `forks_total`
- May cause multicollinearity - consider dropping it or using feature importance analysis

---

## 📚 References

- **Backfill Pipeline**: `src/github_predictor/pipelines/feature_pipeline/backfill_pipeline.py`
- **Daily Pipeline**: `src/github_predictor/pipelines/feature_pipeline/daily_pipeline.py`
- **Feature Enricher**: `src/github_predictor/pipelines/feature_pipeline/feature_enricher.py`
- **Hopsworks Client**: `src/github_predictor/pipelines/feature_pipeline/hopsworks_client.py`

---

**Last Updated**: 2024-12-20
**Status**: HN feature disabled, data consistency issues documented
