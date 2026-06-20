"""Geographic processing module for Kirana store underwriting.

Provides structured geo-feature extraction and location-based risk
scoring.  Competitor proximity, footfall potential, and regional
demographics are modelled through configurable rule-based heuristics
so the pipeline can run end-to-end without external API calls.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature container
# ---------------------------------------------------------------------------

@dataclass
class GeoFeatures:
    """Immutable container for geographic features of a store location.

    Attributes:
        latitude:               Store latitude.
        longitude:              Store longitude.
        population_density:     People per sq-km in the catchment area.
        competitor_count:       Number of competing stores within radius.
        nearest_competitor_km:  Distance to the closest competitor (km).
        footfall_index:         Normalised footfall potential (0.0 – 1.0).
        market_saturation:      Saturation index (0.0 = open, 1.0 = saturated).
        pin_code:               Postal / PIN code string (optional).
        region_tier:            Tier classification (1, 2, 3, …).
        metadata:               Arbitrary extra data for downstream use.
    """

    latitude: float = 0.0
    longitude: float = 0.0
    population_density: float = 0.0
    competitor_count: int = 0
    nearest_competitor_km: float = 0.0
    footfall_index: float = 0.0
    market_saturation: float = 0.0
    pin_code: str = ""
    region_tier: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- convenience helpers ------------------------------------------------

    def is_valid(self) -> bool:
        """Return True when the feature set passes basic sanity checks."""
        return (
            -90.0 <= self.latitude <= 90.0
            and -180.0 <= self.longitude <= 180.0
            and self.population_density >= 0.0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the features to a plain dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "population_density": self.population_density,
            "competitor_count": self.competitor_count,
            "nearest_competitor_km": self.nearest_competitor_km,
            "footfall_index": self.footfall_index,
            "market_saturation": self.market_saturation,
            "pin_code": self.pin_code,
            "region_tier": self.region_tier,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------

class GeoProcessor:
    """Analyzes geographic data for store underwriting.

    Processes location data to determine catchment quality, competitor
    pressure, and regional viability.  Scoring weights are configurable
    through the *config* dict:

        - ``population_weight``   (float) – default 0.25
        - ``competition_weight``  (float) – default 0.25
        - ``footfall_weight``     (float) – default 0.25
        - ``saturation_weight``   (float) – default 0.15
        - ``tier_weight``         (float) – default 0.10
    """

    _DEFAULT_WEIGHTS: Dict[str, float] = {
        "population": 0.25,
        "competition": 0.25,
        "footfall": 0.25,
        "saturation": 0.15,
        "tier": 0.10,
    }

    # Tier multipliers — lower tier ⇒ higher risk discount.
    _TIER_SCORES: Dict[int, float] = {1: 1.0, 2: 0.75, 3: 0.50, 4: 0.30}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the geo processor.

        Args:
            config: Optional configuration overrides for weights and
                    thresholds.
        """
        self.config: Dict[str, Any] = config or {}
        self.weights = self._resolve_weights()
        logger.info("GeoProcessor initialised (weights=%s)", self.weights)

    # -- public API ---------------------------------------------------------

    def extract_features(
        self,
        latitude: float,
        longitude: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> GeoFeatures:
        """Build a ``GeoFeatures`` object for the given coordinates.

        In the current phase this is a **stub** that populates features
        from the optional *context* dict.  Once external geo APIs (Google
        Places, Census, etc.) are integrated, this method will call them.

        Args:
            latitude:  Store latitude.
            longitude: Store longitude.
            context:   Optional pre-fetched geo metadata.

        Returns:
            A populated ``GeoFeatures`` instance.
        """
        ctx = context or {}
        features = GeoFeatures(
            latitude=latitude,
            longitude=longitude,
            population_density=ctx.get("population_density", 0.0),
            competitor_count=ctx.get("competitor_count", 0),
            nearest_competitor_km=ctx.get("nearest_competitor_km", 0.0),
            footfall_index=ctx.get("footfall_index", 0.0),
            market_saturation=ctx.get("market_saturation", 0.0),
            pin_code=ctx.get("pin_code", ""),
            region_tier=ctx.get("region_tier", 3),
            metadata=ctx.get("metadata", {}),
        )
        logger.info(
            "Extracted geo features for (%.4f, %.4f)", latitude, longitude
        )
        return features

    def compute_geo_score(self, features: GeoFeatures) -> float:
        """Compute a normalised geographic viability score.

        Scoring is a weighted combination of:
        - Population density (higher is better, capped at 15 000 / km²).
        - Competition (fewer competitors and greater distance = better).
        - Footfall index (pass-through, already 0-1).
        - Market saturation (lower is better).
        - Region tier (Tier-1 cities score higher).

        Args:
            features: Extracted ``GeoFeatures`` for the store.

        Returns:
            A float between 0.0 (worst) and 1.0 (best).
        """
        if not features.is_valid():
            logger.warning("Invalid geo features – returning 0.0")
            return 0.0

        w = self.weights

        # Population density → 0-1 (cap 15 000).
        norm_pop = min(features.population_density / 15_000.0, 1.0)

        # Competition → 0-1 (fewer and farther = better).
        comp_count_score = max(1.0 - (features.competitor_count / 20.0), 0.0)
        comp_dist_score = min(features.nearest_competitor_km / 5.0, 1.0)
        norm_comp = 0.5 * comp_count_score + 0.5 * comp_dist_score

        # Footfall — already normalised.
        norm_foot = max(0.0, min(features.footfall_index, 1.0))

        # Saturation — invert (low saturation = good).
        norm_sat = max(1.0 - features.market_saturation, 0.0)

        # Tier score.
        norm_tier = self._TIER_SCORES.get(features.region_tier, 0.25)

        score = (
            w["population"] * norm_pop
            + w["competition"] * norm_comp
            + w["footfall"] * norm_foot
            + w["saturation"] * norm_sat
            + w["tier"] * norm_tier
        )

        score = max(0.0, min(score, 1.0))
        logger.info("Geo score computed: %.4f", score)
        return round(score, 4)

    # -- static utilities ---------------------------------------------------

    @staticmethod
    def haversine_distance(
        coord1: Tuple[float, float],
        coord2: Tuple[float, float],
    ) -> float:
        """Compute the great-circle distance between two points (km).

        Args:
            coord1: (latitude, longitude) of point 1.
            coord2: (latitude, longitude) of point 2.

        Returns:
            Distance in kilometres.
        """
        R = 6371.0  # Earth radius in km
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # -- internals ----------------------------------------------------------

    def _resolve_weights(self) -> Dict[str, float]:
        """Merge user-supplied weights with defaults."""
        weights = dict(self._DEFAULT_WEIGHTS)
        for key in weights:
            cfg_key = f"{key}_weight"
            if cfg_key in self.config:
                weights[key] = float(self.config[cfg_key])
        return weights
