"""Machine learning models for Kirana store underwriting.

Provides two XGBoost-based predictive models and a ``ModelRegistry``
to manage them:

- **MarketShareModel**  – predicts estimated market share (0-1) from
  geographic features.
- **CreditScoreModel**  – predicts a credit score (300-900) from the
  full set of feature scores (visual, geo, fraud, inventory, shelf).

Both models ship with ``train()`` placeholders that accept pandas
DataFrames and ``predict()`` methods that work on single feature dicts.
When no trained model is available, deterministic fallback heuristics
are used so the pipeline never breaks.
"""

from __future__ import annotations

import logging
import os
import pickle
from typing import Any, Dict, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports – gracefully degrade if not installed.
try:
    from xgboost import XGBRegressor

    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False
    logger.info("xgboost not installed – falling back to sklearn")

try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import cross_val_score

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False
    logger.warning("sklearn not installed – ML training will be unavailable")


# ---------------------------------------------------------------------------
# MarketShareModel
# ---------------------------------------------------------------------------

class MarketShareModel:
    """Predicts local market share from geographic features.

    Input features (dict keys):
        ``population_density``, ``competitor_count``,
        ``nearest_competitor_km``, ``footfall_index``,
        ``market_saturation``, ``region_tier``

    Output:
        Float in [0.0, 1.0] representing estimated market share.

    Config overrides:
        - ``n_estimators``    (int)   – default 200
        - ``max_depth``       (int)   – default 4
        - ``learning_rate``   (float) – default 0.05
    """

    FEATURE_NAMES: List[str] = [
        "population_density",
        "competitor_count",
        "nearest_competitor_km",
        "footfall_index",
        "market_saturation",
        "region_tier",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._n_est = int(cfg.get("n_estimators", 200))
        self._depth = int(cfg.get("max_depth", 4))
        self._lr = float(cfg.get("learning_rate", 0.05))
        self._model: Optional[Any] = None
        self._is_trained: bool = False
        logger.info("MarketShareModel initialised (trained=%s)", self._is_trained)

    # -- Training -----------------------------------------------------------

    def train(self, X, y) -> Dict[str, Any]:
        """Train the market-share model.

        Args:
            X: Feature matrix – pandas DataFrame or 2-D numpy array
               with columns matching ``FEATURE_NAMES``.
            y: Target array of market-share values (0-1).

        Returns:
            Dict with training metrics (e.g. cv_rmse).
        """
        X_arr = np.asarray(X, dtype=np.float64)
        y_arr = np.asarray(y, dtype=np.float64)

        self._model = self._make_regressor()
        self._model.fit(X_arr, y_arr)
        self._is_trained = True

        metrics: Dict[str, Any] = {"status": "trained", "n_samples": len(y_arr)}

        # Cross-validated RMSE when sklearn is available.
        if _HAS_SKLEARN and len(y_arr) >= 5:
            cv_scores = cross_val_score(
                self._make_regressor(), X_arr, y_arr,
                cv=min(5, len(y_arr)), scoring="neg_root_mean_squared_error",
            )
            metrics["cv_rmse"] = round(float(-cv_scores.mean()), 4)

        logger.info("MarketShareModel trained: %s", metrics)
        return metrics

    def predict(self, features: Dict[str, float]) -> float:
        """Predict market share for a single store.

        Args:
            features: Dict with keys from ``FEATURE_NAMES``.

        Returns:
            Predicted market share clipped to [0.0, 1.0].
        """
        if self._is_trained and self._model is not None:
            vec = self._features_to_array(features)
            raw = float(self._model.predict(vec.reshape(1, -1))[0])
            return max(0.0, min(round(raw, 4), 1.0))

        # Fallback heuristic when no model is trained.
        return self._heuristic_predict(features)

    # -- Persistence --------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialize the trained model to disk."""
        if self._model is None:
            raise RuntimeError("No model to save – call train() first")
        with open(path, "wb") as f:
            pickle.dump({"model": self._model, "is_trained": self._is_trained}, f)
        logger.info("MarketShareModel saved to %s", path)

    def load(self, path: str) -> None:
        """Load a previously saved model."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._model = data["model"]
        self._is_trained = data.get("is_trained", True)
        logger.info("MarketShareModel loaded from %s", path)

    # -- Internals ----------------------------------------------------------

    def _make_regressor(self):
        """Create a fresh regressor instance."""
        if _HAS_XGB:
            return XGBRegressor(
                n_estimators=self._n_est,
                max_depth=self._depth,
                learning_rate=self._lr,
                objective="reg:squarederror",
                verbosity=0,
            )
        if _HAS_SKLEARN:
            return GradientBoostingRegressor(
                n_estimators=self._n_est,
                max_depth=self._depth,
                learning_rate=self._lr,
            )
        raise RuntimeError("Neither xgboost nor sklearn is installed")

    def _features_to_array(self, features: Dict[str, float]) -> np.ndarray:
        return np.array(
            [features.get(k, 0.0) for k in self.FEATURE_NAMES],
            dtype=np.float64,
        )

    @staticmethod
    def _heuristic_predict(f: Dict[str, float]) -> float:
        """Deterministic fallback when no ML model is available."""
        pop = min(f.get("population_density", 0) / 15_000.0, 1.0)
        comp = max(1.0 - f.get("competitor_count", 0) / 20.0, 0.0)
        foot = f.get("footfall_index", 0.0)
        sat = max(1.0 - f.get("market_saturation", 0.0), 0.0)
        raw = 0.30 * pop + 0.25 * comp + 0.25 * foot + 0.20 * sat
        return round(max(0.0, min(raw, 1.0)), 4)


# ---------------------------------------------------------------------------
# CreditScoreModel
# ---------------------------------------------------------------------------

class CreditScoreModel:
    """Predicts a credit score from combined underwriting feature scores.

    Input features (dict keys):
        ``visual_score``, ``geo_score``, ``fraud_score``,
        ``shelf_occupancy``, ``product_count``, ``category_diversity``,
        ``inventory_value_inr``, ``fast_moving_fraction``,
        ``market_share``

    Output:
        Integer credit score in [300, 900].

    Config overrides:
        - ``n_estimators``    (int)   – default 300
        - ``max_depth``       (int)   – default 5
        - ``learning_rate``   (float) – default 0.03
    """

    FEATURE_NAMES: List[str] = [
        "visual_score",
        "geo_score",
        "fraud_score",
        "shelf_occupancy",
        "product_count",
        "category_diversity",
        "inventory_value_inr",
        "fast_moving_fraction",
        "market_share",
    ]

    SCORE_MIN: int = 300
    SCORE_MAX: int = 900

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._n_est = int(cfg.get("n_estimators", 300))
        self._depth = int(cfg.get("max_depth", 5))
        self._lr = float(cfg.get("learning_rate", 0.03))
        self._model: Optional[Any] = None
        self._is_trained: bool = False
        logger.info("CreditScoreModel initialised (trained=%s)", self._is_trained)

    # -- Training -----------------------------------------------------------

    def train(self, X, y) -> Dict[str, Any]:
        """Train the credit-score model.

        Args:
            X: Feature matrix – pandas DataFrame or 2-D numpy array
               with columns matching ``FEATURE_NAMES``.
            y: Target array of credit scores (300-900).

        Returns:
            Dict with training metrics.
        """
        X_arr = np.asarray(X, dtype=np.float64)
        y_arr = np.asarray(y, dtype=np.float64)

        self._model = self._make_regressor()
        self._model.fit(X_arr, y_arr)
        self._is_trained = True

        metrics: Dict[str, Any] = {"status": "trained", "n_samples": len(y_arr)}

        if _HAS_SKLEARN and len(y_arr) >= 5:
            cv_scores = cross_val_score(
                self._make_regressor(), X_arr, y_arr,
                cv=min(5, len(y_arr)), scoring="neg_root_mean_squared_error",
            )
            metrics["cv_rmse"] = round(float(-cv_scores.mean()), 4)

        logger.info("CreditScoreModel trained: %s", metrics)
        return metrics

    def predict(self, features: Dict[str, float]) -> int:
        """Predict credit score for a single store.

        Args:
            features: Dict with keys from ``FEATURE_NAMES``.

        Returns:
            Integer credit score clipped to [300, 900].
        """
        if self._is_trained and self._model is not None:
            vec = self._features_to_array(features)
            raw = float(self._model.predict(vec.reshape(1, -1))[0])
            return self._clip_score(raw)

        return self._heuristic_predict(features)

    # -- Persistence --------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialize the trained model to disk."""
        if self._model is None:
            raise RuntimeError("No model to save – call train() first")
        with open(path, "wb") as f:
            pickle.dump({"model": self._model, "is_trained": self._is_trained}, f)
        logger.info("CreditScoreModel saved to %s", path)

    def load(self, path: str) -> None:
        """Load a previously saved model."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._model = data["model"]
        self._is_trained = data.get("is_trained", True)
        logger.info("CreditScoreModel loaded from %s", path)

    # -- Internals ----------------------------------------------------------

    def _make_regressor(self):
        if _HAS_XGB:
            return XGBRegressor(
                n_estimators=self._n_est,
                max_depth=self._depth,
                learning_rate=self._lr,
                objective="reg:squarederror",
                verbosity=0,
            )
        if _HAS_SKLEARN:
            return GradientBoostingRegressor(
                n_estimators=self._n_est,
                max_depth=self._depth,
                learning_rate=self._lr,
            )
        raise RuntimeError("Neither xgboost nor sklearn is installed")

    def _features_to_array(self, features: Dict[str, float]) -> np.ndarray:
        return np.array(
            [features.get(k, 0.0) for k in self.FEATURE_NAMES],
            dtype=np.float64,
        )

    def _clip_score(self, raw: float) -> int:
        return int(max(self.SCORE_MIN, min(round(raw), self.SCORE_MAX)))

    @staticmethod
    def _heuristic_predict(f: Dict[str, float]) -> int:
        """Deterministic fallback when no ML model is available."""
        vs = f.get("visual_score", 0.5)
        gs = f.get("geo_score", 0.5)
        fs = f.get("fraud_score", 0.0)
        inv = min(f.get("inventory_value_inr", 0.0) / 200_000.0, 1.0)
        fm = f.get("fast_moving_fraction", 0.0)
        ms = f.get("market_share", 0.5)

        positive = 0.25 * vs + 0.20 * gs + 0.15 * inv + 0.15 * fm + 0.10 * ms
        penalty = 0.15 * fs
        raw = max(0.0, min(positive - penalty, 1.0))

        # Map 0-1 → 300-900.
        return int(round(300 + raw * 600))


# ---------------------------------------------------------------------------
# ModelRegistry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Central registry for loading, caching, and accessing ML models.

    Usage::

        registry = ModelRegistry(config)
        ms_model = registry.get_model("market_share")
        cs_model = registry.get_model("credit_score")

    Config overrides:
        - ``model_dir``       (str)  – directory for saved models
        - ``market_share``    (dict) – forwarded to MarketShareModel
        - ``credit_score``    (dict) – forwarded to CreditScoreModel
    """

    _KNOWN_MODELS = {
        "market_share": MarketShareModel,
        "credit_score": CreditScoreModel,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the model registry."""
        self.config: Dict[str, Any] = config or {}
        self._model_dir: str = self.config.get("model_dir", "models")
        self._cache: Dict[str, Any] = {}
        logger.info("ModelRegistry initialised (model_dir=%s)", self._model_dir)

    def get_model(self, model_id: str):
        """Retrieve (or lazily create) a model by its identifier.

        Args:
            model_id: One of ``"market_share"`` or ``"credit_score"``.

        Returns:
            The model instance (``MarketShareModel`` or
            ``CreditScoreModel``).

        Raises:
            KeyError: If *model_id* is not recognised.
        """
        if model_id in self._cache:
            return self._cache[model_id]

        if model_id not in self._KNOWN_MODELS:
            raise KeyError(
                f"Unknown model '{model_id}'. "
                f"Available: {list(self._KNOWN_MODELS.keys())}"
            )

        model_cls = self._KNOWN_MODELS[model_id]
        model_cfg = self.config.get(model_id, {})
        model = model_cls(config=model_cfg)

        # Auto-load from disk if a saved model exists.
        model_path = os.path.join(self._model_dir, f"{model_id}.pkl")
        if os.path.isfile(model_path):
            model.load(model_path)
            logger.info("Auto-loaded saved model: %s", model_path)

        self._cache[model_id] = model
        return model

    def list_models(self) -> List[str]:
        """Return the list of known model identifiers."""
        return list(self._KNOWN_MODELS.keys())
