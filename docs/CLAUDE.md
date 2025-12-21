# GitHub Trend Predictor - Project Spec


## 🎯 What We're Building

**Input:** GitHub repository data (stars, language, velocity)  
**Output:** "Will this repo trend in next 7 days?" (Yes/No + probability)  
**Value:** Discover trending technologies 7 days early

---

## 📋 Requirements Checklist

### ✅ Must-Have (Pass Grade)

- [ ] **Dynamic Data Source:** GitHub Trending API (updates daily)
- [ ] **No Kaggle:** Using free public API
- [ ] **External Features:** stars_velocity, fork_rate, language, age
- [ ] **Prediction:** Binary classification (trending yes/no)
- [ ] **Feature Pipeline:** Daily data fetch → Hopsworks
- [ ] **Training Pipeline:** Weekly model training (XGBoost)
- [ ] **Inference Pipeline:** Daily predictions
- [ ] **UI:** Gradio dashboard showing top 20 predictions

### 🌟 A-Grade Additions

- [ ] **LLM Integration:** Claude API explains trends in natural language
- [ ] **Model Comparison:** Base model vs. enhanced (with velocity features)

---

## 🏗️ System Architecture (Simple)

```
GitHub API → Feature Pipeline (daily) → Hopsworks Feature Store
                                              ↓
                                    Training Pipeline (weekly)
                                              ↓
                                        Model Registry
                                              ↓
                                    Inference Pipeline (daily)
                                              ↓
                                    Gradio UI + Claude Insights
```

---

## 📊 Data Pipeline

### Input Features
| Feature | Description | Importance |
|---------|-------------|------------|
| `stars_today` | Stars gained today | HIGH |
| `total_stars` | Total stars | Medium |
| `language` | Programming language | Medium |
| `stars_velocity` | stars/day since creation | HIGH |
| `fork_rate` | forks/stars ratio | Low |

### Target Label
- `is_trending`: 1 if in top 25 trending within 7 days, else 0

### Feature Engineering
```python
stars_velocity = stars_today / max(days_old, 1)
fork_rate = forks / max(total_stars, 1)
popularity_score = stars_today * 0.5 + total_stars * 0.3 + forks * 0.2
```

---

## 🔄 4 Core Pipelines

### 1. Feature Backfill
**Run once:** Load 90 days of historical data  
**Command:** `uv run backfill`  
**Output:** ~3,000 records in Hopsworks

### 2. Daily Features
**Run daily:** Fetch today's trending repos  
**Command:** `uv run daily-features`  
**Output:** ~100-200 new records/day

### 3. Training
**Run weekly:** Train XGBoost classifier  
**Command:** `uv run train`  
**Target:** >80% accuracy

### 4. Inference
**Run daily:** Generate predictions  
**Command:** `uv run predict`  
**Output:** Top 50 repos with probabilities

---

## 🎯 Expected Outputs

### 1. Feature Store (Hopsworks)
- Feature group: `github_trending`
- ~3,000+ rows, 9 features
- Daily updates

### 2. Model
- XGBoost Classifier
- Accuracy: >80%
- Saved in Model Registry

### 3. Predictions
- Daily: Top 50 repos likely to trend
- Format: repo_name, probability, language

### 4. User Interface
```
┌─────────────────────────────────┐
│ Top Predicted Trending Repos   │
├────┬─────────────────┬──────────┤
│ 1  │ microsoft/ts    │ 87.3%   │
│ 2  │ vercel/next.js  │ 84.1%   │
│ 3  │ pytorch/tune    │ 81.5%   │
└────┴─────────────────┴──────────┘

🤖 Claude's Insight:
"TypeScript tools dominating..."
```

---

## 🚀 Quick Start

```bash
# 1. Setup
uv sync
cp .env.example .env
# Edit .env with HOPSWORKS_API_KEY

# 2. Initial data load
uv run backfill

# 3. Train model
uv run train

# 4. Generate predictions
uv run predict

# 5. Launch UI
uv run serve
```

---

## 📅 Timeline (3 Weeks)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| **1** | Setup, backfill, daily pipeline | Data flowing to Hopsworks |
| **2** | Training, inference pipelines | Model trained, predictions working |
| **3** | UI, Claude integration, polish | Complete system, demo ready |

---

## 🔑 Required API Keys

1. **Hopsworks** (required): app.hopsworks.ai
2. **GitHub** (optional): github.com/settings/tokens
3. **Anthropic** (A-grade): console.anthropic.com

---

## ✅ Success Criteria

| Metric | Target | Actual |
|--------|--------|--------|
| Model Accuracy | >80% | ___ |
| Daily Predictions | 50 repos | ___ |
| UI Functionality | Working dashboard | ___ |
| LLM Integration | Claude insights | ___ |

---

## 🐛 Common Issues

**Problem:** GitHub API rate limit  
**Solution:** Use trending API (no auth needed) or add GITHUB_API_KEY

**Problem:** Hopsworks connection fails  
**Solution:** Check API key in .env, verify project name

**Problem:** Not enough training data  
**Solution:** Wait 7 days or reduce LOOKBACK_DAYS to 30

---

## 📚 Key Resources

- **Course:** ID2223 KTH
- **GitHub Trending API:** `gh-trending-api.herokuapp.com`
- **Hopsworks:** `app.hopsworks.ai`
- **UV Docs:** `docs.astral.sh/uv`

---

## 📝 Notes

- Model retrains weekly (Sundays)
- Predictions update daily (12:00 UTC)
- Feature store updates daily (12:00 UTC)
- UI hosted on Hugging Face Spaces (free)

---

**Last Updated:** Dec 20, 2024  
**Status:** In Development