# Data Pipeline Flow

## Backfill Pipeline (One-Time)

```
For each day (30 days):

  1. Fetch GH Archive data (hours 12, 23)
     └─> Returns ~115k repos with star_velocity & commit_frequency

  2. Select top 50 repos by star_velocity
     └─> These are "trending" for that day

  3. Cache GH Archive data (optimization)
     └─> Avoid re-downloading for each repo

  4. Enrich 50 repos with features
     ├─> GitHub API: stars_total, forks_total, language
     ├─> GH Archive (from cache): star_velocity, commit_frequency
     └─> Computed: days_old, fork_rate, popularity_score

  5. Store unlabeled features

After all days collected:

  6. Label data with 7-day lookback
     └─> is_trending = 1 if repo appeared in trending during next 7 days

  7. Upload ~1,550 labeled samples to Hopsworks
```

## Daily Pipeline (Runs Every Day)

```
Today (e.g., Dec 20):

  1. Scrape github.com/trending
     └─> Get ~25 trending repo names

  2. Enrich repos with features
     ├─> Fetch GH Archive ONCE for all repos (cached)
     ├─> For each repo: GitHub API + lookup in cache
     └─> Result: 25 repos with 11 features

  3. Save as unlabeled_2024-12-20.csv

  4. Check for 7-day-old data
     └─> If unlabeled_2024-12-13.csv exists:
         ├─> Label it (check trending Dec 14-20)
         ├─> Upload to Hopsworks
         └─> Delete unlabeled file
```

## Cache Optimization

**Without Cache:**
- Download GH Archive for EACH repo → 50 × 300MB = 15GB, 55 minutes

**With Cache:**
- Download GH Archive ONCE → cache 115k repos → lookup for each repo
- Result: 300MB, 71 seconds
- **46x faster, 50x less bandwidth**

## Data Timeline

```
Dec 13: Backfill → collect & save unlabeled
Dec 14: Backfill → collect & save unlabeled
  ...
Dec 13: Backfill → collect & save unlabeled
        ↓
        Label all (7-day lookback) → Upload to Hopsworks ✅

Dec 20: Daily → collect & save unlabeled_2024-12-20.csv
        ↓
        Find unlabeled_2024-12-13.csv → Label → Upload ✅

Dec 27: Daily → collect & save unlabeled_2024-12-27.csv
        ↓
        Find unlabeled_2024-12-20.csv → Label → Upload ✅
```

## Key Features

| Feature | Description | Source |
|---------|-------------|--------|
| `stars_total` | Total stars | GitHub API |
| `star_velocity` | Stars gained in 24h (extrapolated) | GH Archive |
| `commit_frequency` | Commits in 24h (extrapolated) | GH Archive |
| `language` | Programming language | GitHub API |
| `days_old` | Repo age | Computed |
| `fork_rate` | forks / stars | Computed |
| `is_trending` | Trended in next 7 days? (0/1) | TrendingLabeler |

## Sampling Strategy

- **Backfill**: Top 50 repos by `star_velocity` from GH Archive (algorithmic)
- **Daily**: Repos from `github.com/trending` (GitHub's curated list)
- **GH Archive**: Sample hours [12, 23] → extrapolate 12x to estimate 24h totals
- **Labeling**: 7-day lookback to create `is_trending` labels
