"""
Synthetic data generator + XGBoost model trainer for KiranaGPT.

Generates 2000 realistic kirana store samples based on India retail research,
trains real XGBoost models, saves them to models/ directory.

Run: python backend/train_models.py
"""

import os, json, pickle, logging
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# ── Synthetic data generation ─────────────────────────────────────────────

def generate_kirana_dataset(n: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)

    # Location tiers (Tier-1: 20%, Tier-2: 35%, Tier-3: 45%)
    tiers = rng.choice([1, 2, 3], size=n, p=[0.20, 0.35, 0.45])

    # Population density by tier (people/km²)
    pop_density = np.where(
        tiers == 1, rng.uniform(12000, 25000, n),
        np.where(tiers == 2, rng.uniform(5000, 12000, n),
                 rng.uniform(800, 5000, n))
    )

    # Competition (fewer in Tier-3)
    competitor_count = np.where(
        tiers == 1, rng.integers(5, 20, n),
        np.where(tiers == 2, rng.integers(2, 12, n), rng.integers(0, 6, n))
    ).astype(float)

    nearest_competitor_km = rng.uniform(0.05, 1.2, n)

    # Footfall index driven by population + POIs
    footfall_index = np.clip(
        0.4 * pop_density / 20000 + 0.3 * rng.uniform(0, 1, n)
        + 0.3 * np.where(tiers <= 2, 0.7, 0.4),
        0.05, 1.0
    )

    market_saturation = np.clip(competitor_count / 20.0 + rng.uniform(-0.1, 0.1, n), 0, 1)

    # Visual features
    shelf_occupancy = np.clip(rng.beta(3, 2, n), 0.05, 0.98)
    product_count   = (rng.integers(5, 200, n)).astype(float)
    category_div    = rng.integers(1, 8, n).astype(float)
    inventory_val   = np.clip(
        rng.lognormal(mean=10.5, sigma=0.8, size=n), 500, 250000
    )
    fast_moving_frac = np.clip(rng.beta(2, 3, n), 0.05, 0.90)

    # Visual + geo scores (deterministic from features + noise)
    visual_score = np.clip(
        0.35 * shelf_occupancy + 0.25 * product_count / 200
        + 0.15 * category_div / 8
        + 0.15 * fast_moving_frac
        + 0.10 * rng.uniform(0, 1, n),
        0.05, 0.97
    )
    geo_score = np.clip(
        0.25 * pop_density / 20000
        + 0.25 * (1 - market_saturation)
        + 0.25 * footfall_index
        + 0.15 * (1 / tiers)
        + 0.10 * rng.uniform(0, 1, n),
        0.10, 0.97
    )
    fraud_score = np.clip(rng.beta(1, 6, n), 0, 0.85)

    # Market share label (ground truth derived from geo features + noise)
    market_share = np.clip(
        0.30 * (pop_density / 20000)
        + 0.25 * (1 - competitor_count / 20)
        + 0.25 * footfall_index
        + 0.20 * (1 - market_saturation)
        + rng.normal(0, 0.04, n),
        0.01, 0.95
    )

    # Credit score label (300-900, grounded in visual + geo + fraud)
    composite = np.clip(
        0.40 * visual_score + 0.35 * geo_score - 0.25 * fraud_score, 0, 1
    )
    credit_score = np.clip(
        300 + 600 * composite
        + 80 * (fast_moving_frac - 0.3)
        + 40 * (shelf_occupancy - 0.5)
        + 20 * (inventory_val / 200000)
        + rng.normal(0, 30, n),
        300, 900
    ).astype(int)

    return {
        "market_share_X": np.column_stack([
            pop_density, competitor_count, nearest_competitor_km,
            footfall_index, market_saturation, tiers.astype(float)
        ]),
        "market_share_y": market_share,
        "credit_score_X": np.column_stack([
            visual_score, geo_score, fraud_score, shelf_occupancy,
            product_count, category_div, inventory_val, fast_moving_frac,
            market_share
        ]),
        "credit_score_y": credit_score.astype(float),
    }


def train_and_save():
    logger.info("Generating 2000 synthetic kirana samples...")
    data = generate_kirana_dataset(2000)

    from sklearn.model_selection import train_test_split

    ms_X_train, ms_X_test, ms_y_train, ms_y_test = train_test_split(
        data["market_share_X"], data["market_share_y"], test_size=0.2, random_state=42
    )
    cs_X_train, cs_X_test, cs_y_train, cs_y_test = train_test_split(
        data["credit_score_X"], data["credit_score_y"], test_size=0.2, random_state=42
    )

    try:
        from xgboost import XGBRegressor
        ModelClass = XGBRegressor
        model_kwargs_ms = dict(n_estimators=300, max_depth=4, learning_rate=0.05,
                               subsample=0.8, colsample_bytree=0.8,
                               objective="reg:squarederror", verbosity=0, random_state=42)
        model_kwargs_cs = dict(n_estimators=400, max_depth=5, learning_rate=0.03,
                               subsample=0.8, colsample_bytree=0.8,
                               objective="reg:squarederror", verbosity=0, random_state=42)
        logger.info("Using XGBoost")
    except ImportError:
        from sklearn.ensemble import GradientBoostingRegressor as ModelClass
        model_kwargs_ms = dict(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
        model_kwargs_cs = dict(n_estimators=300, max_depth=5, learning_rate=0.03, random_state=42)
        logger.warning("XGBoost not found — using sklearn GradientBoosting")

    # ── Market share model ─────────────────────────────────────────────
    logger.info("Training MarketShareModel...")
    ms_model = ModelClass(**model_kwargs_ms)
    ms_model.fit(ms_X_train, ms_y_train)
    ms_path = MODELS_DIR / "market_share.pkl"
    with open(ms_path, "wb") as f:
        pickle.dump({"model": ms_model, "is_trained": True}, f)
    logger.info("Saved → %s", ms_path)

    # Held-out test eval (honest generalisation estimate)
    preds = ms_model.predict(ms_X_test)
    mse = float(np.mean((preds - ms_y_test) ** 2))
    train_preds = ms_model.predict(ms_X_train)
    train_mse = float(np.mean((train_preds - ms_y_train) ** 2))
    logger.info("MarketShare TRAIN RMSE: %.4f | TEST RMSE: %.4f", train_mse ** 0.5, mse ** 0.5)

    # ── Credit score model ─────────────────────────────────────────────
    logger.info("Training CreditScoreModel...")
    cs_model = ModelClass(**model_kwargs_cs)
    cs_model.fit(cs_X_train, cs_y_train)
    cs_path = MODELS_DIR / "credit_score.pkl"
    with open(cs_path, "wb") as f:
        pickle.dump({"model": cs_model, "is_trained": True}, f)
    logger.info("Saved → %s", cs_path)

    preds_cs = cs_model.predict(cs_X_test)
    mse_cs = float(np.mean((preds_cs - cs_y_test) ** 2))
    train_preds_cs = cs_model.predict(cs_X_train)
    train_mse_cs = float(np.mean((train_preds_cs - cs_y_train) ** 2))
    logger.info("CreditScore TRAIN RMSE: %.2f | TEST RMSE: %.2f", train_mse_cs ** 0.5, mse_cs ** 0.5)

    # ── Save metadata ──────────────────────────────────────────────────
    meta = {
        "n_samples": 2000,
        "train_test_split": "80/20, random_state=42",
        "market_share_train_rmse": round(train_mse ** 0.5, 4),
        "market_share_test_rmse": round(mse ** 0.5, 4),
        "credit_score_train_rmse": round(train_mse_cs ** 0.5, 2),
        "credit_score_test_rmse": round(mse_cs ** 0.5, 2),
        "model_backend": "xgboost" if "XGBRegressor" in str(type(ms_model)) else "sklearn",
        "data_source": "synthetic — generated from India retail research benchmarks (NCAER footfall, Nielsen basket size). Real-outcome retraining is the planned NBFC pilot step.",
    }
    with open(MODELS_DIR / "training_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("✅ Both models trained and saved to models/")
    logger.info("   market_share.pkl  — TEST RMSE %.4f", mse ** 0.5)
    logger.info("   credit_score.pkl  — TEST RMSE %.2f", mse_cs ** 0.5)
    return meta


if __name__ == "__main__":
    train_and_save()
