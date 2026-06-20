"""Fraud detection module for Kirana store underwriting."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .visual_processor import VisualFeatures
from .geo_processor import GeoFeatures

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Severity levels for fraud flags."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FraudFlag:
    """A single fraud indicator raised by a detection rule."""
    rule_id: str
    severity: Severity
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "description": self.description,
            "evidence": self.evidence,
        }


class FraudDetector:
    """Identifies potential fraudulent patterns in store data.

    Uses rule-based cross-checks between visual, geographic, and
    financial signals.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the fraud detector."""
        self.config: Dict[str, Any] = config or {}
        self._min_shelf_occ = self.config.get("min_shelf_occupancy", 0.10)
        self._max_competitors = self.config.get("max_competitor_ratio", 15)
        self._min_products = int(self.config.get("min_product_count", 5))
        logger.info("FraudDetector initialised")

    def check_for_anomalies(
        self,
        visual_features: VisualFeatures,
        geo_features: GeoFeatures,
        financial_data: Optional[Dict[str, Any]] = None,
    ) -> List[FraudFlag]:
        """Run all fraud-detection rules and return raised flags."""
        flags: List[FraudFlag] = []
        fin = financial_data or {}

        flags.extend(self._check_visual(visual_features))
        flags.extend(self._check_geo(geo_features))
        flags.extend(self._check_cross(visual_features, geo_features, fin))

        logger.info("Fraud check – %d flag(s) raised", len(flags))
        return flags

    def compute_fraud_score(self, flags: List[FraudFlag]) -> float:
        """Derive a normalised fraud-risk score (0 = clean, 1 = high risk)."""
        sev_w = {Severity.LOW: 0.15, Severity.MEDIUM: 0.4,
                 Severity.HIGH: 0.7, Severity.CRITICAL: 1.0}
        raw = sum(sev_w.get(f.severity, 0.0) for f in flags)
        score = min(raw / 2.0, 1.0)
        logger.info("Fraud risk score: %.4f (%d flags)", score, len(flags))
        return round(score, 4)

    # -- rules --------------------------------------------------------------

    def _check_visual(self, vf: VisualFeatures) -> List[FraudFlag]:
        flags: List[FraudFlag] = []
        if vf.shelf_occupancy < self._min_shelf_occ:
            flags.append(FraudFlag(
                "VISUAL_SHELF_EMPTY", Severity.HIGH,
                "Shelf occupancy is suspiciously low.",
                {"shelf_occupancy": vf.shelf_occupancy},
            ))
        if vf.product_count < self._min_products:
            flags.append(FraudFlag(
                "VISUAL_LOW_PRODUCTS", Severity.MEDIUM,
                f"YOLOv8 model detected very few products ({vf.product_count}) in the store images.",
                {"raw_detection_count": vf.product_count},
            ))
        if vf.lighting_quality < 0.15:
            flags.append(FraudFlag(
                "VISUAL_POOR_LIGHTING", Severity.LOW,
                "Extremely poor lighting may indicate a non-functional store.",
                {"lighting_quality": vf.lighting_quality},
            ))

        # Check diagnostics for blur, duplicates, and genuine angle verification
        diags = vf.metadata.get("diagnostics", {})
        
        # Check duplicate images
        dup_pairs = []
        for key, diag in diags.items():
            dup_of = diag.get("duplicate_of")
            if dup_of:
                dup_pairs.append((key, dup_of))
                
        if dup_pairs:
            flags.append(FraudFlag(
                "VISUAL_IMAGE_DUPLICATED", Severity.CRITICAL,
                f"Duplicate images detected: {', '.join([f'{k} is identical to {v}' for k, v in dup_pairs])}.",
                {"duplicate_pairs": dup_pairs}
            ))

        # Check blurry images
        blurry_keys = []
        for key, diag in diags.items():
            if diag.get("is_blurry", False):
                blurry_keys.append(key)
        if blurry_keys:
            flags.append(FraudFlag(
                "VISUAL_IMAGE_BLURRY", Severity.HIGH,
                f"Extremely blurry images uploaded in slots: {', '.join(blurry_keys)}.",
                {"blurry_keys": blurry_keys}
            ))

        # Check genuine angle verification
        mismatched_keys = []
        for key, diag in diags.items():
            angle_chk = diag.get("genuine_angle_check", {})
            if angle_chk and not angle_chk.get("is_genuine_angle", True):
                mismatched_keys.append(f"{key} ({angle_chk.get('details', '')})")
        if mismatched_keys:
            flags.append(FraudFlag(
                "VISUAL_IMAGE_ANGLE_MISMATCH", Severity.HIGH,
                f"Images uploaded do not match standard shelf layout/angles: {', '.join(mismatched_keys)}.",
                {"mismatched_keys": mismatched_keys}
            ))

        return flags

    def _check_geo(self, gf: GeoFeatures) -> List[FraudFlag]:
        flags: List[FraudFlag] = []
        if gf.competitor_count > self._max_competitors:
            flags.append(FraudFlag(
                "GEO_OVERSATURATED", Severity.MEDIUM,
                "Extremely high competitor density.",
                {"competitor_count": gf.competitor_count},
            ))
        if gf.market_saturation > 0.90:
            flags.append(FraudFlag(
                "GEO_MARKET_SATURATED", Severity.HIGH,
                "Market is near-fully saturated.",
                {"market_saturation": gf.market_saturation},
            ))
        # Hyper-competitive check
        if gf.market_saturation > 0.85 and gf.competitor_count > 12:
            flags.append(FraudFlag(
                "GEO_HYPER_COMPETITIVE", Severity.MEDIUM,
                "Hyper-competitive location: High market saturation with numerous competitors.",
                {"competitor_count": gf.competitor_count, "market_saturation": gf.market_saturation}
            ))
        return flags

    def _check_cross(self, vf: VisualFeatures, gf: GeoFeatures,
                     fin: Dict[str, Any]) -> List[FraudFlag]:
        flags: List[FraudFlag] = []
        
        claimed = fin.get("claimed_tier")
        if claimed is not None and claimed < gf.region_tier:
            flags.append(FraudFlag(
                "CROSS_TIER_MISMATCH", Severity.MEDIUM,
                "Claimed region tier does not match geo-derived tier.",
                {"claimed_tier": claimed, "actual_tier": gf.region_tier},
            ))

        # Rent to Revenue Check (CRITICAL)
        rent = fin.get("rent")
        inv_summary = vf.metadata.get("inventory_summary", {})
        inv_value = inv_summary.get("inventory_value_inr", 1000)
        fm = inv_summary.get("fast_moving_fraction", 0.2)
        cat_counts = inv_summary.get("category_counts", {})
        sku_diversity = sum(1 for v in cat_counts.values() if v > 0) / max(len(cat_counts), 1)
        
        # Calculate estimated monthly revenue consistent with app.py
        est_rev = int(
            inv_value * (1 + fm * 3) * 30 
            * (0.5 + gf.footfall_index) * (0.8 + sku_diversity * 0.5)
        )
        
        # Only run the critical rent-to-revenue check if the rent was explicitly provided by the user (i.e. not None)
        if rent is not None and est_rev > 0:
            rent_ratio = rent / est_rev
            if rent_ratio > 0.40:
                flags.append(FraudFlag(
                    "CROSS_RENT_TO_REVENUE_CRITICAL", Severity.CRITICAL,
                    f"Monthly rent (₹{rent:,}) is dangerously high relative to estimated store revenue (₹{est_rev:,}): {rent_ratio*100:.1f}%.",
                    {"rent": rent, "estimated_revenue": est_rev, "rent_ratio": rent_ratio}
                ))

        # Claimed Shop Size vs Detected Items Mismatch
        shop_size = fin.get("shop_size")
        total_items = inv_summary.get("total_items", 0)
        if shop_size is not None and shop_size > 800 and total_items < 15:
            flags.append(FraudFlag(
                "CROSS_SIZE_TO_ITEMS_MISMATCH", Severity.HIGH,
                f"Large shop size claimed ({shop_size} sq ft) but extremely few items ({total_items}) were detected.",
                {"shop_size": shop_size, "product_count": total_items}
            ))

        return flags
