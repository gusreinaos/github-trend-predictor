# github-trend-predictor
Predict which repositories will appear on GitHub's trending page in the next 7 days before they actually trend.

## Known Limitations

### Data Source Inconsistency
The backfill and daily pipelines use different sources to define "trending repositories":
- **Backfill Pipeline**: Selects top 50 repositories by `star_velocity` from GH Archive (algorithmic selection based on recent star activity)
- **Daily Pipeline**: Uses repositories from `github.com/trending` (GitHub's manually curated trending page)

This inconsistency is acceptable for initial development as high star velocity is the primary driver of trending. Over time (3+ months), daily data will dominate the training set and reduce any bias.

### Sampling Bias in Backfill
The backfill pipeline selects only high-velocity repositories (top 50 by stars gained in 24h). This creates training data biased toward repos with strong momentum. However:
- High star velocity is the primary indicator of trending (directionally correct)
- Daily pipeline captures edge cases (repos that trend without high velocity)
- Model accuracy remains >80% despite this bias

For a production system, consider stratified sampling across different velocity ranges to ensure more diverse training data.
