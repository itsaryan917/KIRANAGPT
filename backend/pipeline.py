"""Main underwriting pipeline for Kirana stores.

Provides two pipeline classes:

- **KiranaUnderwriter** – core underwriting engine (image → detection →
  shelf → inventory → visual features → geo → scoring → fraud → fusion).
- **KiranaPipeline** – top-level orchestrator that wraps
  ``KiranaUnderwriter`` and appends ML-model predictions
  (``MarketShareModel``, ``CreditScoreModel``), returning a unified
  result dict.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .image_loader import ImageLoader, LoadedImageSet, REQUIRED_IMAGE_KEYS
from .detector import YOLODetector, Detection
from .shelf import ShelfAnalyzer, ShelfMetrics, WallShelfResult, MULTI_WALL_KEYS
from .inventory import InventoryEstimator, InventoryEstimate
from .visual_processor import VisualProcessor, VisualFeatures
from .geo import GeoFeatureExtractor
from .geo_processor import GeoProcessor, GeoFeatures
from .fraud import FraudDetector
from .fusion import FusionModel, UnderwritingProfile
from .ml_models import MarketShareModel, CreditScoreModel, ModelRegistry

logger = logging.getLogger(__name__)


class KiranaUnderwriter:
    """End-to-end underwriting pipeline for a single Kirana store.

    Usage::

        underwriter = KiranaUnderwriter(config)
        profile = underwriter.run({
            "store_id": "K-12345",
            "image_paths": {
                "front":        "imgs/front.jpg",
                "billing_area": "imgs/billing.jpg",
                "left_wall":    "imgs/left_wall.jpg",
                "centre_wall":  "imgs/centre_wall.jpg",
                "right_wall":   "imgs/right_wall.jpg",
            },
            "latitude": 19.076,
            "longitude": 72.877,
            "financial_data": { ... },
        })
        print(profile.decision)   # APPROVE / REVIEW / REJECT

    Config sub-keys forwarded to components:
        ``image_loader``, ``detector``, ``shelf``, ``inventory``,
        ``visual``, ``geo_extractor``, ``geo``, ``fraud``, ``fusion``.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize all sub-processors.

        Args:
            config: Master config dict.  Sub-keys are forwarded to the
                    respective component.
        """
        cfg = config or {}

        # CV components – need a model path for the detector.
        self._detector_model: str = cfg.get("detector_model", "yolov8n.pt")
        self._detector_cfg: Dict[str, Any] = cfg.get("detector", {})

        self._shelf = ShelfAnalyzer(cfg.get("shelf", {}))
        self._inventory = InventoryEstimator(cfg.get("inventory", {}))
        self._visual = VisualProcessor(cfg.get("visual", {}))

        # Geo components.
        self._geo_extractor = GeoFeatureExtractor(cfg.get("geo_extractor", {}))
        self._geo = GeoProcessor(cfg.get("geo", {}))

        # Decision components.
        self._fraud = FraudDetector(cfg.get("fraud", {}))
        self._fusion = FusionModel(cfg.get("fusion", {}))

        # Lazy-init detector (model load is expensive).
        self._detector: Optional[YOLODetector] = None
        self._img_loader_cfg: Dict[str, Any] = cfg.get("image_loader", {})

        logger.info("KiranaUnderwriter initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_data: Dict[str, Any]) -> UnderwritingProfile:
        """Execute the full underwriting pipeline.

        Args:
            input_data: Must contain:
                - ``store_id``       (str)
                - ``image_paths``    (dict[str, str])  – 5 required keys
                - ``latitude``       (float)
                - ``longitude``      (float)
                - ``financial_data`` (dict, optional)

        Returns:
            A fully populated ``UnderwritingProfile``.

        Raises:
            ValueError: If required fields are missing.
        """
        start = time.monotonic()
        self._validate(input_data)

        store_id: str = input_data["store_id"]
        logger.info("▶ Pipeline started for store %s", store_id)

        # ── 1. Load & preprocess images ──────────────────────────────
        loaded = self._run_image_loader(input_data["image_paths"])

        # ── 2. Object detection ──────────────────────────────────────
        detections = self._run_detector(loaded)

        # ── 3. Shelf analysis (on the centre_wall image) ──────────────
        shelf_metrics = self._run_shelf(loaded)

        # ── 4. Inventory estimation ──────────────────────────────────
        inventory = self._inventory.estimate(
            detections, sdi_raw=shelf_metrics.sdi_raw,
        )

        # ── 5. Build VisualFeatures from shelf + inventory + diag ────
        visual_features = self._build_visual_features(
            shelf_metrics, inventory, detections, loaded,
        )

        # ── 6. Geo feature extraction & scoring ─────────────────────
        geo_result = self._geo_extractor.extract(
            input_data["latitude"], input_data["longitude"],
        )
        geo_features = self._geo_extractor.to_geo_features(geo_result)
        geo_score = self._geo.compute_geo_score(geo_features)

        # ── 7. Visual scoring ────────────────────────────────────────
        visual_score = self._visual.compute_visual_score(visual_features)

        # ── 8. Fraud detection ───────────────────────────────────────
        financial = input_data.get("financial_data", {})
        fraud_flags = self._fraud.check_for_anomalies(
            visual_features, geo_features, financial,
        )
        fraud_score = self._fraud.compute_fraud_score(fraud_flags)

        # ── 9. Fusion & decision ─────────────────────────────────────
        profile = self._fusion.fuse(
            store_id=store_id,
            visual_score=visual_score,
            geo_score=geo_score,
            fraud_score=fraud_score,
            fraud_flags=fraud_flags,
        )

        elapsed = time.monotonic() - start
        profile.metadata["pipeline_elapsed_s"] = round(elapsed, 3)
        profile.metadata["shelf_metrics"] = shelf_metrics.to_dict()
        profile.metadata["inventory"] = inventory.to_dict()
        profile.metadata["geo_extraction"] = geo_result.to_dict()
        profile.metadata["views_used"] = [
            "front", "left_wall", "centre_wall", "right_wall",
        ]

        logger.info(
            "✔ Pipeline complete for %s in %.3fs → %s (composite=%.4f)",
            store_id, elapsed, profile.decision, profile.composite_score,
        )
        return profile

    # ------------------------------------------------------------------
    # VisualFeatures bridge
    # ------------------------------------------------------------------

    @staticmethod
    def _build_visual_features(
        shelf: ShelfMetrics,
        inventory: InventoryEstimate,
        detections: List[Detection],
        loaded: LoadedImageSet,
    ) -> VisualFeatures:
        """Convert ShelfAnalyzer + InventoryEstimator outputs into a
        ``VisualFeatures`` dataclass.

        Field mapping:
            shelf_occupancy    ← ShelfMetrics.sdi_raw
            product_count      ← InventoryEstimate.total_items
            category_diversity ← number of non-zero categories in
                                 InventoryEstimate.category_counts
            store_cleanliness  ← ShelfMetrics.sdi_uniformity (uniform
                                 stocking is a proxy for tidiness)
            signage_visible    ← True if the "front" image loaded OK
                                 and had decent brightness
            lighting_quality   ← average brightness across all loaded
                                 images, normalised to 0-1
            raw_detections     ← serialised Detection list
            metadata           ← full shelf + inventory detail

        Args:
            shelf:      Output of ``ShelfAnalyzer.analyze()``.
            inventory:  Output of ``InventoryEstimator.estimate()``.
            detections: Raw ``Detection`` objects from the YOLO detector.
            loaded:     ``LoadedImageSet`` from the image loader (for
                        diagnostics like brightness and signage status).

        Returns:
            A fully populated ``VisualFeatures`` instance.
        """
        # -- shelf_occupancy -----------------------------------------------
        shelf_occupancy = shelf.sdi_raw

        # -- product_count -------------------------------------------------
        product_count = inventory.total_items

        # -- category_diversity --------------------------------------------
        category_diversity = sum(
            1 for cnt in inventory.category_counts.values() if cnt > 0
        )

        # -- store_cleanliness (sdi_uniformity as proxy) -------------------
        store_cleanliness = shelf.sdi_uniformity

        # -- signage_visible (derived from 'front' exterior image) ----------
        front_diag = loaded.diagnostics.get("front", {})
        signage_loaded = "error" not in front_diag
        signage_bright = front_diag.get("brightness_mean", 0.0) > 50.0
        signage_visible = signage_loaded and signage_bright

        # -- lighting_quality ----------------------------------------------
        brightness_values = [
            diag.get("brightness_mean", 0.0)
            for diag in loaded.diagnostics.values()
            if "brightness_mean" in diag
        ]
        if brightness_values:
            # Normalise mean brightness to 0-1 (0=black, 255=white).
            avg_brightness = sum(brightness_values) / len(brightness_values)
            lighting_quality = min(avg_brightness / 200.0, 1.0)
        else:
            lighting_quality = 0.0

        # -- raw_detections ------------------------------------------------
        raw_detections = [d.to_dict() for d in detections]

        # -- metadata (full audit trail) -----------------------------------
        metadata: Dict[str, Any] = {
            "shelf_metrics": shelf.to_dict(),
            "inventory_summary": inventory.to_dict(),
            "zone_sdi": shelf.zone_sdi,
            "sdi_depth": round(shelf.sdi_depth, 4),
            "fast_moving_fraction": round(inventory.fast_moving_fraction, 4),
            "inventory_value_inr": round(inventory.inventory_value_inr, 2),
            "front_diag": front_diag,
            "image_count": len(loaded.images),
            "all_images_valid": loaded.all_valid,
            "diagnostics": loaded.diagnostics,
        }

        features = VisualFeatures(
            shelf_occupancy=round(shelf_occupancy, 4),
            product_count=product_count,
            category_diversity=category_diversity,
            store_cleanliness=round(store_cleanliness, 4),
            signage_visible=signage_visible,
            lighting_quality=round(lighting_quality, 4),
            raw_detections=raw_detections,
            metadata=metadata,
        )

        logger.info(
            "VisualFeatures built: occupancy=%.3f, products=%d, "
            "categories=%d, cleanliness=%.3f, signage=%s, lighting=%.3f",
            features.shelf_occupancy,
            features.product_count,
            features.category_diversity,
            features.store_cleanliness,
            features.signage_visible,
            features.lighting_quality,
        )
        return features

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------

    def _run_image_loader(
        self, image_paths: Dict[str, str]
    ) -> LoadedImageSet:
        """Load and preprocess the five required store-view images."""
        loader = ImageLoader(image_paths, config=self._img_loader_cfg)
        loaded = loader.load()
        if not loaded.all_valid:
            logger.warning(
                "Some images failed to load – pipeline will continue "
                "with available images"
            )
        return loaded

    def _run_detector(self, loaded: LoadedImageSet) -> List[Detection]:
        """Run YOLO detection across all loaded images.

        Detections from every image are merged into a single list.
        """
        if self._detector is None:
            self._detector = YOLODetector(
                self._detector_model, config=self._detector_cfg,
            )

        all_detections: List[Detection] = []
        for key, img in loaded.images.items():
            dets = self._detector.detect(img)
            logger.debug("Detected %d objects in [%s]", len(dets), key)
            all_detections.extend(dets)

        logger.info(
            "Total detections across %d images: %d",
            len(loaded.images), len(all_detections),
        )
        return all_detections

    def _run_shelf(self, loaded: LoadedImageSet) -> ShelfMetrics:
        """Run shelf analysis on all interior wall images with overlap correction.

        Processes ``left_wall``, ``centre_wall``, ``right_wall``, and
        ``billing_area`` independently, then fuses the results using
        ``ShelfAnalyzer.combine_multi_wall()``.  Adjacent wall pairs
        (left↔centre, centre↔right) share a 12% edge strip that is
        averaged and counted exactly once in the combined output.

        Falls back gracefully when individual images are missing.
        """
        wall_results: Dict[str, WallShelfResult] = {}

        for key in MULTI_WALL_KEYS:
            img = loaded.images.get(key)
            if img is None:
                logger.warning(
                    "Image '%s' not available – skipping in shelf analysis", key
                )
                continue
            wall_results[key] = self._shelf.analyze_with_edges(img, key)

        if not wall_results:
            logger.warning(
                "No wall images available – returning default ShelfMetrics"
            )
            return ShelfMetrics()

        return self._shelf.combine_multi_wall(wall_results)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(data: Dict[str, Any]) -> None:
        """Ensure required fields are present."""
        required = ["store_id", "image_paths", "latitude", "longitude"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(
                f"Missing required fields: {', '.join(missing)}"
            )


# ======================================================================
# KiranaPipeline – top-level orchestrator with ML predictions
# ======================================================================

class KiranaPipeline:
    """Top-level pipeline that combines underwriting + ML predictions.

    Wraps ``KiranaUnderwriter`` for the core underwriting decision, then
    runs ``MarketShareModel`` and ``CreditScoreModel`` on the extracted
    features to produce a unified result.

    Usage::

        pipeline = KiranaPipeline(config)
        result = pipeline.run({
            "store_id": "K-12345",
            "image_paths": {
                "front":        "imgs/front.jpg",
                "billing_area": "imgs/billing.jpg",
                "left_wall":    "imgs/left_wall.jpg",
                "centre_wall":  "imgs/centre_wall.jpg",
                "right_wall":   "imgs/right_wall.jpg",
            },
            "latitude": 19.076,
            "longitude": 72.877,
            "financial_data": { ... },
        })

        print(result["underwriting_output"]["decision"])  # APPROVE
        print(result["ml_outputs"]["credit_score"])        # 720
        print(result["ml_outputs"]["market_share"])         # 0.34

    Config sub-keys:
        - All ``KiranaUnderwriter`` config keys (forwarded as-is).
        - ``ml_models``  (dict) – forwarded to ``ModelRegistry``.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the full pipeline.

        Args:
            config: Master config dict.
        """
        cfg = config or {}

        # Core underwriting engine (reuses all existing logic).
        self._underwriter = KiranaUnderwriter(cfg)

        # ML model registry.
        ml_cfg = cfg.get("ml_models", {})
        self._registry = ModelRegistry(ml_cfg)
        self._market_share_model = self._registry.get_model("market_share")
        self._credit_score_model = self._registry.get_model("credit_score")

        logger.info("KiranaPipeline initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the full pipeline: underwriting + ML predictions.

        Args:
            input_data: Same schema as ``KiranaUnderwriter.run()``:
                - ``store_id``       (str)
                - ``image_paths``    (dict[str, str])
                - ``latitude``       (float)
                - ``longitude``      (float)
                - ``financial_data`` (dict, optional)

        Returns:
            A dict with two top-level keys::

                {
                    "underwriting_output": { <UnderwritingProfile fields> },
                    "ml_outputs": {
                        "credit_score": int,
                        "market_share": float,
                    },
                }
        """
        start = time.monotonic()
        store_id = input_data.get("store_id", "unknown")
        logger.info("▶ KiranaPipeline started for store %s", store_id)

        # ── Step 1: Run core underwriting ─────────────────────────────
        profile: UnderwritingProfile = self._underwriter.run(input_data)

        # ── Step 2: Extract geo features for market-share model ──────
        geo_features = self._extract_geo_features(profile, input_data)

        # ── Step 3: Predict market share ─────────────────────────────
        market_share = self._market_share_model.predict(geo_features)
        logger.info("Market share prediction: %.4f", market_share)

        # ── Step 4: Build credit-score feature vector ────────────────
        credit_features = self._build_credit_features(
            profile, market_share,
        )

        # ── Step 5: Predict credit score ─────────────────────────────
        credit_score = self._credit_score_model.predict(credit_features)
        logger.info("Credit score prediction: %d", credit_score)

        # ── Step 6: Assemble result ──────────────────────────────────
        elapsed = time.monotonic() - start

        result: Dict[str, Any] = {
            "underwriting_output": profile.to_dict(),
            "ml_outputs": {
                "credit_score": credit_score,
                "market_share": round(market_share, 4),
            },
            "pipeline_metadata": {
                "store_id": store_id,
                "total_elapsed_s": round(elapsed, 3),
            },
        }

        logger.info(
            "✔ KiranaPipeline complete for %s in %.3fs → "
            "decision=%s, credit=%d, market_share=%.4f",
            store_id, elapsed, profile.decision,
            credit_score, market_share,
        )
        return result

    # ------------------------------------------------------------------
    # Feature extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_geo_features(
        profile: UnderwritingProfile,
        input_data: Dict[str, Any],
    ) -> Dict[str, float]:
        """Build the feature dict expected by ``MarketShareModel``.

        Pulls geo data from the underwriting profile metadata (which
        was populated by ``KiranaUnderwriter``) and falls back to
        input_data for coordinates.
        """
        geo_meta = profile.metadata.get("geo_extraction", {})
        pop = geo_meta.get("population", {})
        comp = geo_meta.get("competition", {})

        # Derive population density from ring totals.
        total_pop = pop.get("total", 0)
        import math
        area_km2 = math.pi  # π × 1 km²
        pop_density = total_pop / area_km2 if area_km2 > 0 else 0.0

        # Competitor count.
        competitor_count = (
            comp.get("kirana_count_1km", 0)
            + comp.get("supermarket_count", 0)
        )

        # Nearest competitor distance in km.
        nearest_km = comp.get("nearest_competitor_m", 0.0) / 1000.0

        # Footfall and saturation from profile metadata if available,
        # otherwise derive from geo_extraction.
        poi = geo_meta.get("poi", {})
        poi_total = sum(poi.values()) if poi else 0
        footfall_raw = (
            0.4 * min(total_pop / 5000.0, 1.0)
            + 0.3 * min(poi_total / 15.0, 1.0)
            + 0.3 * 0.5  # default road factor
        )
        footfall_index = max(0.0, min(footfall_raw, 1.0))

        sat_raw = min(
            (comp.get("kirana_count_1km", 0)
             + comp.get("supermarket_count", 0) * 3) / 25.0,
            1.0,
        )

        # Region tier from pop density.
        if pop_density > 10_000:
            tier = 1
        elif pop_density > 4_000:
            tier = 2
        else:
            tier = 3

        return {
            "population_density": round(pop_density, 1),
            "competitor_count": competitor_count,
            "nearest_competitor_km": round(nearest_km, 3),
            "footfall_index": round(footfall_index, 4),
            "market_saturation": round(sat_raw, 4),
            "region_tier": tier,
        }

    @staticmethod
    def _build_credit_features(
        profile: UnderwritingProfile,
        market_share: float,
    ) -> Dict[str, float]:
        """Build the feature dict expected by ``CreditScoreModel``.

        Pulls scores from the underwriting profile and enriches with
        shelf / inventory metadata.
        """
        meta = profile.metadata
        shelf = meta.get("shelf_metrics", {})
        inv = meta.get("inventory", {})

        return {
            "visual_score": profile.visual_score,
            "geo_score": profile.geo_score,
            "fraud_score": profile.fraud_score,
            "shelf_occupancy": shelf.get("sdi_raw", 0.0),
            "product_count": inv.get("total_items", 0),
            "category_diversity": len(
                [v for v in inv.get("category_counts", {}).values() if v > 0]
            ),
            "inventory_value_inr": inv.get("inventory_value_inr", 0.0),
            "fast_moving_fraction": inv.get("fast_moving_fraction", 0.0),
            "market_share": market_share,
        }
