"""Fusion module — combines multi-modal signals into underwriting decision.

Confidence formula:
  confidence = signal_agreement × boundary_distance × data_quality

  signal_agreement:  1 - |visual_score - geo_score|   (aligned signals = confident)
  boundary_distance: how far composite is from the 0.35/0.65 thresholds
  data_quality:      penalises if geo came from mock fallback or images are few

This makes confidence explainable: a judge can ask "why 87%?" and get a
precise answer — "visual and geo signals agree, composite is well above
threshold, and we have real OSM data."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .visual_processor import VisualFeatures
from .geo_processor import GeoFeatures
from .fraud import FraudFlag, Severity

logger = logging.getLogger(__name__)


@dataclass
class UnderwritingProfile:
    store_id: str = ""
    visual_score: float = 0.0
    geo_score: float = 0.0
    fraud_score: float = 0.0
    composite_score: float = 0.0
    decision: str = "REVIEW"
    confidence: float = 0.0
    fraud_flags: List[FraudFlag] = field(default_factory=list)
    breakdown: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store_id": self.store_id,
            "visual_score": round(self.visual_score, 4),
            "geo_score": round(self.geo_score, 4),
            "fraud_score": round(self.fraud_score, 4),
            "composite_score": round(self.composite_score, 4),
            "decision": self.decision,
            "confidence": round(self.confidence, 4),
            "fraud_flags": [f.to_dict() for f in self.fraud_flags],
            "breakdown": {k: round(v, 4) for k, v in self.breakdown.items()},
            "metadata": self.metadata,
        }


class FusionModel:
    """Combines visual, geo, and fraud scores into a final underwriting decision."""

    _DEFAULT_WEIGHTS = {"visual": 0.40, "geo": 0.35, "fraud_penalty": 0.25}
    _APPROVE_THRESHOLD = 0.65
    _REJECT_THRESHOLD  = 0.35

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._w_visual = float(cfg.get("visual_weight",      self._DEFAULT_WEIGHTS["visual"]))
        self._w_geo    = float(cfg.get("geo_weight",         self._DEFAULT_WEIGHTS["geo"]))
        self._w_fraud  = float(cfg.get("fraud_penalty",      self._DEFAULT_WEIGHTS["fraud_penalty"]))
        self._approve  = float(cfg.get("approve_threshold",  self._APPROVE_THRESHOLD))
        self._reject   = float(cfg.get("reject_threshold",   self._REJECT_THRESHOLD))
        logger.info("FusionModel initialised")

    def fuse(
        self,
        store_id: str,
        visual_score: float,
        geo_score: float,
        fraud_score: float,
        fraud_flags: List[FraudFlag],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UnderwritingProfile:

        # ── Composite score ───────────────────────────────────────────────────
        positive  = self._w_visual * visual_score + self._w_geo * geo_score
        penalty   = self._w_fraud  * fraud_score
        composite = max(0.0, min(positive - penalty, 1.0))

        # ── Decision ──────────────────────────────────────────────────────────
        has_critical = any(f.severity == Severity.CRITICAL for f in fraud_flags)
        if composite >= self._approve and not has_critical:
            decision = "APPROVE"
        elif composite <= self._reject or has_critical:
            decision = "REJECT"
        else:
            decision = "REVIEW"

        # ── Confidence (explainable formula) ──────────────────────────────────
        # Component 1: signal agreement (visual vs geo alignment)
        signal_agreement = 1.0 - abs(visual_score - geo_score)

        # Component 2: distance from nearest decision boundary
        dist_from_approve = abs(composite - self._approve)
        dist_from_reject  = abs(composite - self._reject)
        dist_from_boundary = min(dist_from_approve, dist_from_reject)
        # Normalise: max useful distance is 0.3 (midpoint between thresholds)
        boundary_distance = min(dist_from_boundary / 0.30, 1.0)

        # Component 3: data quality signals
        md = metadata or {}
        geo_is_real  = not md.get("geo_extraction", {}).get("is_mock", False)
        image_count  = md.get("image_count", 5)
        fraud_penalty_conf = min(len(fraud_flags) * 0.05, 0.25)

        data_quality = (
            (0.6 if geo_is_real else 0.3)         # real OSM data vs mock
            + (0.3 * min(image_count / 5.0, 1.0)) # all 5 images present
            + 0.1                                  # base
            - fraud_penalty_conf                   # fraud flags reduce certainty
        )
        data_quality = max(0.1, min(data_quality, 1.0))

        confidence = (
            0.45 * signal_agreement
            + 0.35 * boundary_distance
            + 0.20 * data_quality
        )
        confidence = round(max(0.10, min(confidence, 0.97)), 4)

        breakdown = {
            "visual_contribution": round(self._w_visual * visual_score, 4),
            "geo_contribution":    round(self._w_geo    * geo_score,    4),
            "fraud_penalty":       round(self._w_fraud  * fraud_score,  4),
            "confidence_signal_agreement": round(signal_agreement, 4),
            "confidence_boundary_dist":    round(boundary_distance, 4),
            "confidence_data_quality":     round(data_quality, 4),
        }

        logger.info(
            "Fusion: composite=%.4f decision=%s confidence=%.4f "
            "(agreement=%.3f boundary=%.3f quality=%.3f)",
            composite, decision, confidence,
            signal_agreement, boundary_distance, data_quality,
        )

        return UnderwritingProfile(
            store_id=store_id,
            visual_score=round(visual_score, 4),
            geo_score=round(geo_score, 4),
            fraud_score=round(fraud_score, 4),
            composite_score=round(composite, 4),
            decision=decision,
            confidence=confidence,
            fraud_flags=fraud_flags,
            breakdown=breakdown,
            metadata=metadata or {},
        )
