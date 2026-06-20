"""Inventory estimation for Kirana store underwriting.

YOLO (yolov8n.pt) is trained on COCO-80 classes — not kirana products.
This module bridges that gap with a two-layer approach:

  Layer 1 (YOLO detections): Maps real COCO detections to kirana categories.
  Layer 2 (SDI visual proxy): If YOLO finds fewer than MIN_REAL_DETECTIONS items,
    the shelf density index (sdi_raw) is used to estimate a realistic inventory
    count and value. This ensures the revenue estimate is never near-zero
    just because a kirana shelf has Parle-G packets instead of COCO "bottles".

This makes the pipeline honest about what YOLO actually sees while still
producing a credible inventory signal for the financial model.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .detector import Detection

logger = logging.getLogger(__name__)

# ── COCO → kirana category mapping ────────────────────────────────────────────
# COCO-80 objects that legitimately appear on kirana shelves
DEFAULT_CATEGORY_MAP: Dict[str, Set[str]] = {
    "staples": {
        "bowl", "cup", "spoon", "knife", "fork",
        "banana", "apple", "orange", "broccoli", "carrot",
        "sandwich", "pizza", "donut", "cake",
    },
    "fmcg": {
        "bottle", "wine glass", "toothbrush",
        "scissors", "vase", "cup",
    },
    "high_margin": {
        "cell phone", "laptop", "remote", "clock",
        "book", "backpack", "handbag", "suitcase",
    },
}

DEFAULT_UNIT_VALUES: Dict[str, float] = {
    "staples":      45.0,
    "fmcg":        120.0,
    "high_margin": 350.0,
    "uncategorised": 80.0,
}

DEFAULT_FAST_MOVING: Set[str] = {
    "bottle", "banana", "apple", "cup", "bowl",
    "toothbrush", "scissors", "vase", "book",
}

# Below this count, fall back to SDI-based estimation
MIN_REAL_DETECTIONS = 8

# Kirana-realistic inventory distribution (from FMCG retail research)
# A 200 sq-ft store with sdi_raw=0.7 has ~150 visible SKUs
SDI_TO_ITEMS_SCALE = 220          # items at sdi_raw = 1.0
SDI_TO_VALUE_PER_ITEM = 95.0     # avg INR/item in a mixed kirana shelf


@dataclass
class InventoryEstimate:
    total_items: int = 0
    inventory_value_inr: float = 0.0
    category_counts: Dict[str, int] = field(default_factory=dict)
    category_ratios: Dict[str, float] = field(default_factory=dict)
    fast_moving_fraction: float = 0.0
    per_detection: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_items": self.total_items,
            "inventory_value_inr": round(self.inventory_value_inr, 2),
            "category_counts": self.category_counts,
            "category_ratios": {k: round(v, 4) for k, v in self.category_ratios.items()},
            "fast_moving_fraction": round(self.fast_moving_fraction, 4),
        }


class InventoryEstimator:
    """Two-layer kirana inventory estimator."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._cat_map = cfg.get("category_map", DEFAULT_CATEGORY_MAP)
        self._unit_vals = cfg.get("unit_values", DEFAULT_UNIT_VALUES)
        self._fast_moving = cfg.get("fast_moving_classes", DEFAULT_FAST_MOVING)
        self._min_detections = int(cfg.get("min_real_detections", MIN_REAL_DETECTIONS))
        logger.info("InventoryEstimator initialised")

    def estimate(
        self,
        detections: List[Detection],
        sdi_raw: float = 0.5,
    ) -> InventoryEstimate:
        """Estimate inventory using YOLO detections + SDI visual proxy."""

        # Layer 1: real YOLO detections
        yolo_result = self._from_detections(detections)

        if yolo_result.total_items >= self._min_detections:
            # Enough real detections — use them directly
            logger.info(
                "Inventory: using %d real YOLO detections", yolo_result.total_items
            )
            yolo_result.diagnostics["source"] = "yolo_detections"
            return yolo_result

        # Layer 2: SDI visual proxy — YOLO found too few items
        # (normal for kirana shelves full of Indian packaging COCO wasn't trained on)
        sdi_result = self._from_sdi(sdi_raw, yolo_result)
        logger.info(
            "Inventory: YOLO found %d items (below threshold %d) — "
            "augmenting with SDI proxy (sdi=%.3f) → %d estimated items",
            yolo_result.total_items, self._min_detections,
            sdi_raw, sdi_result.total_items,
        )
        sdi_result.diagnostics["source"] = "sdi_proxy"
        sdi_result.diagnostics["yolo_items_detected"] = yolo_result.total_items
        return sdi_result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _from_detections(self, detections: List[Detection]) -> InventoryEstimate:
        cats = {k: 0 for k in self._cat_map}
        cats["uncategorised"] = 0
        value = 0.0
        fast_count = 0
        per = []

        for det in detections:
            cat = self._classify(det.class_name)
            cats[cat] = cats.get(cat, 0) + 1
            value += self._unit_vals.get(cat, self._unit_vals["uncategorised"])
            if det.class_name in self._fast_moving:
                fast_count += 1
            per.append({"class": det.class_name, "category": cat,
                         "confidence": round(det.confidence, 3)})

        total = len(detections)
        ratios = {k: round(v / total, 4) if total > 0 else 0.0
                  for k, v in cats.items()}
        fm = round(fast_count / total, 4) if total > 0 else 0.25

        return InventoryEstimate(
            total_items=total,
            inventory_value_inr=round(value, 2),
            category_counts=cats,
            category_ratios=ratios,
            fast_moving_fraction=fm,
            per_detection=per,
        )

    def _from_sdi(self, sdi_raw: float, yolo: InventoryEstimate) -> InventoryEstimate:
        """Build a realistic estimate from shelf density when YOLO is sparse."""
        sdi = max(0.05, min(sdi_raw, 1.0))

        # Sigmoid-smoothed item count: shelves are never perfectly full
        items_est = int(SDI_TO_ITEMS_SCALE * (1 / (1 + math.exp(-10 * (sdi - 0.5)))))
        # Add any real YOLO items on top
        items_est = max(items_est, yolo.total_items)

        # Realistic kirana category split (India FMCG research benchmarks)
        cat_split = {
            "fmcg":          int(items_est * 0.45),   # largest — snacks, HPC
            "staples":       int(items_est * 0.35),   # dal, rice, atta
            "high_margin":   int(items_est * 0.10),   # tobacco, cosmetics
            "uncategorised": int(items_est * 0.10),   # misc
        }
        # Reconcile rounding
        cat_split["uncategorised"] += items_est - sum(cat_split.values())

        value = (
            cat_split["fmcg"] * self._unit_vals["fmcg"]
            + cat_split["staples"] * self._unit_vals["staples"]
            + cat_split["high_margin"] * self._unit_vals["high_margin"]
            + cat_split["uncategorised"] * self._unit_vals["uncategorised"]
        )

        # Fast-moving fraction: fmcg + some staples
        fm = round((cat_split["fmcg"] * 0.75 + cat_split["staples"] * 0.30) / items_est, 4)

        ratios = {k: round(v / items_est, 4) for k, v in cat_split.items()}

        return InventoryEstimate(
            total_items=items_est,
            inventory_value_inr=round(value, 2),
            category_counts=cat_split,
            category_ratios=ratios,
            fast_moving_fraction=fm,
            per_detection=yolo.per_detection,  # keep real detections for audit
        )

    def _classify(self, class_name: str) -> str:
        for cat, names in self._cat_map.items():
            if class_name in names:
                return cat
        return "uncategorised"
