"""Shelf density analysis module for Kirana store underwriting.

Computes the **Shelf Density Index (SDI)** family of metrics from store
shelf images using low-level CV heuristics (no trained ML model needed):

- **SDI_raw**         – overall shelf occupancy via HSV saturation masking.
- **Zone SDI**        – per-zone (top / eye-level / bottom) occupancy.
- **SDI_uniformity**  – consistency of stocking across wall segments.
- **SDI_depth**       – perceived shelf depth via Laplacian focus variance.

All scores are normalised to **0.0 – 1.0** (higher = better stocked).

Multi-wall mode (``analyze_with_edges`` + ``combine_multi_wall``) processes
all four interior images — left_wall, centre_wall, right_wall, billing_area —
and corrects for the edge overlap between adjacent walls so that the shared
corner strips are counted exactly once in the combined output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

# HSV saturation thresholds for "product-present" mask.
DEFAULT_SAT_LOW: int = 40
DEFAULT_SAT_HIGH: int = 255

# Vertical zone splits (fractions of image height).
ZONE_SPLITS: Dict[str, Tuple[float, float]] = {
    "top": (0.00, 0.33),
    "eye": (0.33, 0.66),
    "bottom": (0.66, 1.00),
}

# Number of equal-width wall segments for uniformity analysis.
DEFAULT_WALL_SEGMENTS: int = 5

# Laplacian depth: reference variance for a "fully sharp" shelf.
DEFAULT_DEPTH_REF_VAR: float = 500.0

# ---------------------------------------------------------------------------
# Multi-wall analysis constants
# ---------------------------------------------------------------------------

# Fraction of image width treated as the shared edge strip with its neighbour.
DEFAULT_OVERLAP_FRACTION: float = 0.12

# Relative contribution weight of billing_area vs a full wall image.
DEFAULT_BILLING_WEIGHT: float = 0.50

# Ordered image keys for multi-wall analysis.
MULTI_WALL_KEYS: Tuple[str, ...] = (
    "left_wall", "centre_wall", "right_wall", "billing_area"
)

# Adjacent wall pairs that share an overlapping edge strip.
# Each tuple is (left_image_key, right_image_key) — the right edge of the
# left image overlaps with the left edge of the right image.
WALL_ADJACENCY: Tuple[Tuple[str, str], ...] = (
    ("left_wall", "centre_wall"),
    ("centre_wall", "right_wall"),
)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class ShelfMetrics:
    """Container for all shelf-density metrics.

    Attributes:
        sdi_raw:           Overall shelf occupancy ratio (0-1).
        zone_sdi:          Per-zone occupancy – keys ``top``, ``eye``,
                           ``bottom``.
        sdi_uniformity:    Stocking consistency across wall segments (0-1,
                           1 = perfectly uniform).
        sdi_depth:         Perceived depth / focus score (0-1).
        wall_segment_sdis: Raw per-segment SDI values used to derive
                           uniformity.
        diagnostics:       Extra debug information.
    """

    sdi_raw: float = 0.0
    zone_sdi: Dict[str, float] = field(default_factory=dict)
    sdi_uniformity: float = 0.0
    sdi_depth: float = 0.0
    wall_segment_sdis: List[float] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:  # type: ignore[override]
        """Serialize to a plain dictionary."""
        return {
            "sdi_raw": round(self.sdi_raw, 4),
            "zone_sdi": {k: round(v, 4) for k, v in self.zone_sdi.items()},
            "sdi_uniformity": round(self.sdi_uniformity, 4),
            "sdi_depth": round(self.sdi_depth, 4),
            "wall_segment_sdis": [round(v, 4) for v in self.wall_segment_sdis],
        }


# ---------------------------------------------------------------------------
# Per-wall result (multi-wall mode)
# ---------------------------------------------------------------------------

@dataclass
class WallShelfResult:
    """Shelf analysis for one wall image, including edge-strip SDIs.

    Attributes:
        key:            Image slot key (e.g. ``"centre_wall"``).
        metrics:        Full ``ShelfMetrics`` computed for this image.
        edge_left_sdi:  SDI of the leftmost ``overlap_fraction`` strip.
                        Used to de-duplicate the edge it shares with its
                        left neighbour.
        edge_right_sdi: SDI of the rightmost ``overlap_fraction`` strip.
                        Used to de-duplicate the edge it shares with its
                        right neighbour.
        weight:         Relative contribution weight in the combined output
                        (1.0 for wall images, ``billing_weight`` for
                        billing_area).
    """

    key: str
    metrics: ShelfMetrics
    edge_left_sdi: float
    edge_right_sdi: float
    weight: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "key": self.key,
            "metrics": self.metrics.to_dict(),
            "edge_left_sdi": round(self.edge_left_sdi, 4),
            "edge_right_sdi": round(self.edge_right_sdi, 4),
            "weight": self.weight,
        }


# ---------------------------------------------------------------------------
# ShelfAnalyzer
# ---------------------------------------------------------------------------

class ShelfAnalyzer:
    """Analyses store shelf images to produce SDI metrics.

    Usage::

        analyzer = ShelfAnalyzer()
        metrics  = analyzer.analyze(shelf_bgr_image)
        print(metrics.sdi_raw, metrics.zone_sdi, metrics.sdi_uniformity)

    Config overrides (via *config* dict):
        - ``sat_low``            (int)   – HSV saturation lower bound, default 40
        - ``sat_high``           (int)   – HSV saturation upper bound, default 255
        - ``wall_segments``      (int)   – number of horizontal segments, default 5
        - ``depth_ref_var``      (float) – Laplacian reference variance, default 500
        - ``overlap_fraction``   (float) – edge strip width as fraction of image
                                           width, default 0.12
        - ``billing_area_weight``(float) – relative weight of billing_area in
                                           combined metrics, default 0.50
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the shelf analyzer.

        Args:
            config: Optional parameter overrides.
        """
        cfg = config or {}
        self._sat_low: int = int(cfg.get("sat_low", DEFAULT_SAT_LOW))
        self._sat_high: int = int(cfg.get("sat_high", DEFAULT_SAT_HIGH))
        self._wall_segs: int = int(cfg.get("wall_segments", DEFAULT_WALL_SEGMENTS))
        self._depth_ref: float = float(cfg.get("depth_ref_var", DEFAULT_DEPTH_REF_VAR))
        self._overlap_frac: float = float(
            cfg.get("overlap_fraction", DEFAULT_OVERLAP_FRACTION)
        )
        self._billing_weight: float = float(
            cfg.get("billing_area_weight", DEFAULT_BILLING_WEIGHT)
        )
        logger.info(
            "ShelfAnalyzer initialised (sat=%d-%d, segs=%d, depth_ref=%.0f, "
            "overlap=%.2f, billing_weight=%.2f)",
            self._sat_low, self._sat_high, self._wall_segs, self._depth_ref,
            self._overlap_frac, self._billing_weight,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, image: np.ndarray) -> ShelfMetrics:
        """Run the full shelf-density analysis on a single image.

        Args:
            image: BGR numpy array of a shelf photograph.

        Returns:
            A populated ``ShelfMetrics`` instance.

        Raises:
            ValueError: If the image is invalid.
        """
        self._validate(image)
        h, w = image.shape[:2]

        # 1. Build the saturation mask.
        sat_mask = self._build_saturation_mask(image)

        # 2. SDI_raw – overall occupancy.
        sdi_raw = self._compute_mask_ratio(sat_mask)

        # 3. Zone SDI – per vertical zone.
        zone_sdi = self._compute_zone_sdi(sat_mask, h)

        # 4. Wall-segment SDIs + uniformity.
        seg_sdis = self._compute_segment_sdis(sat_mask, w)
        sdi_uniformity = self._compute_uniformity(seg_sdis)

        # 5. SDI_depth via Laplacian variance.
        sdi_depth = self._compute_depth(image)

        metrics = ShelfMetrics(
            sdi_raw=sdi_raw,
            zone_sdi=zone_sdi,
            sdi_uniformity=sdi_uniformity,
            sdi_depth=sdi_depth,
            wall_segment_sdis=seg_sdis,
            diagnostics={
                "image_shape": (h, w),
                "sat_range": (self._sat_low, self._sat_high),
                "wall_segments": self._wall_segs,
            },
        )

        logger.info(
            "Shelf analysis complete – SDI_raw=%.3f, uniformity=%.3f, "
            "depth=%.3f, zones=%s",
            sdi_raw, sdi_uniformity, sdi_depth,
            {k: round(v, 3) for k, v in zone_sdi.items()},
        )
        return metrics

    # ------------------------------------------------------------------
    # Step 1 – Saturation mask
    # ------------------------------------------------------------------

    def _build_saturation_mask(self, image: np.ndarray) -> np.ndarray:
        """Create a binary mask where saturated (colourful) pixels = product.

        Products on shelves tend to have higher colour saturation than
        bare wall / empty shelf backgrounds.

        Returns:
            A single-channel ``uint8`` mask (255 = product, 0 = empty).
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        s_channel = hsv[:, :, 1]

        _, mask = cv2.threshold(
            s_channel, self._sat_low, 255, cv2.THRESH_BINARY
        )

        # Light morphological close to fill small gaps in product regions.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    # ------------------------------------------------------------------
    # Step 2 – SDI_raw
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_mask_ratio(mask: np.ndarray) -> float:
        """Return the fraction of non-zero pixels in a binary mask."""
        total = mask.size
        if total == 0:
            return 0.0
        return float(np.count_nonzero(mask)) / total

    # ------------------------------------------------------------------
    # Step 3 – Zone SDI
    # ------------------------------------------------------------------

    def _compute_zone_sdi(
        self, mask: np.ndarray, img_height: int
    ) -> Dict[str, float]:
        """Compute SDI for each vertical zone (top / eye / bottom).

        Args:
            mask:       Full-image binary saturation mask.
            img_height: Height of the image in pixels.

        Returns:
            Dict mapping zone name → SDI ratio.
        """
        zone_sdi: Dict[str, float] = {}
        for zone_name, (frac_start, frac_end) in ZONE_SPLITS.items():
            y_start = int(img_height * frac_start)
            y_end = int(img_height * frac_end)
            zone_strip = mask[y_start:y_end, :]
            zone_sdi[zone_name] = self._compute_mask_ratio(zone_strip)
        return zone_sdi

    # ------------------------------------------------------------------
    # Step 4 – Wall-segment SDIs + uniformity
    # ------------------------------------------------------------------

    def _compute_segment_sdis(
        self, mask: np.ndarray, img_width: int
    ) -> List[float]:
        """Split the mask into equal-width vertical segments and compute
        the SDI for each.

        Returns:
            A list of per-segment SDI values.
        """
        seg_w = max(img_width // self._wall_segs, 1)
        sdis: List[float] = []

        for i in range(self._wall_segs):
            x_start = i * seg_w
            x_end = (
                (i + 1) * seg_w if i < self._wall_segs - 1 else img_width
            )
            segment = mask[:, x_start:x_end]
            sdis.append(self._compute_mask_ratio(segment))

        return sdis

    @staticmethod
    def _compute_uniformity(segment_sdis: List[float]) -> float:
        """Derive a uniformity score from per-segment SDI values.

        Uniformity = 1 − normalised standard deviation.  A perfectly
        uniform shelf scores 1.0; high variance scores near 0.0.

        Args:
            segment_sdis: List of per-segment SDI ratios.

        Returns:
            Float between 0.0 and 1.0.
        """
        if len(segment_sdis) < 2:
            return 1.0

        arr = np.array(segment_sdis, dtype=np.float64)
        mean = float(np.mean(arr))
        if mean == 0.0:
            # All segments empty → technically "uniform" but meaningless.
            return 0.0

        # Coefficient of variation, capped at 1.0.
        cv = float(np.std(arr)) / mean
        uniformity = max(0.0, 1.0 - cv)
        return uniformity

    # ------------------------------------------------------------------
    # Step 5 – SDI_depth (Laplacian variance)
    # ------------------------------------------------------------------

    def _compute_depth(self, image: np.ndarray) -> float:
        """Estimate perceived shelf depth using Laplacian focus variance.

        A well-stocked, deep shelf produces more high-frequency detail
        (textures of products at various depths) and therefore a higher
        Laplacian variance.

        Returns:
            Normalised depth score (0-1).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(np.var(laplacian))

        # Normalise against reference variance.
        depth = min(lap_var / self._depth_ref, 1.0)
        logger.debug("Laplacian variance=%.2f → depth=%.4f", lap_var, depth)
        return depth

    # ------------------------------------------------------------------
    # Multi-wall API
    # ------------------------------------------------------------------

    def analyze_with_edges(
        self, image: np.ndarray, key: str
    ) -> WallShelfResult:
        """Run full shelf analysis on one image and capture edge-strip SDIs.

        The edge strips (leftmost and rightmost ``overlap_fraction`` of the
        image width) are computed from the same saturation mask used for
        ``sdi_raw``, so no extra CV work is needed.

        Args:
            image: BGR numpy array for this wall view.
            key:   Image slot key (``"left_wall"``, ``"centre_wall"``,
                   ``"right_wall"``, or ``"billing_area"``).

        Returns:
            A ``WallShelfResult`` containing the full ``ShelfMetrics`` plus
            left/right edge SDIs and the image's contribution weight.
        """
        self._validate(image)
        metrics = self.analyze(image)

        # Reuse the saturation mask for edge strip SDIs (cheap).
        sat_mask = self._build_saturation_mask(image)
        w = image.shape[1]
        strip_w = max(int(w * self._overlap_frac), 1)

        edge_left = self._compute_mask_ratio(sat_mask[:, :strip_w])
        edge_right = self._compute_mask_ratio(sat_mask[:, w - strip_w:])

        weight = self._billing_weight if key == "billing_area" else 1.0

        logger.info(
            "analyze_with_edges [%s]: sdi_raw=%.3f, edge_L=%.3f, "
            "edge_R=%.3f, weight=%.2f",
            key, metrics.sdi_raw, edge_left, edge_right, weight,
        )
        return WallShelfResult(
            key=key,
            metrics=metrics,
            edge_left_sdi=edge_left,
            edge_right_sdi=edge_right,
            weight=weight,
        )

    def combine_multi_wall(
        self,
        wall_results: Dict[str, "WallShelfResult"],
    ) -> ShelfMetrics:
        """Combine per-wall ``WallShelfResult`` objects into one ``ShelfMetrics``.

        **Overlap-correction algorithm**

        Each pair of adjacent walls shares a physical corner that appears in
        both images:

        - ``left_wall``   right edge  ↔  ``centre_wall`` left edge
        - ``centre_wall`` right edge  ↔  ``right_wall``  left edge

        To avoid double-counting those corners we decompose each image into
        three regions (using ``overlap_fraction`` *f*):

        1. **Left edge strip** (width *f*):  shared with the left neighbour.
        2. **Inner region**   (width 1−f_L−f_R): unique to this image.
        3. **Right edge strip** (width *f*):  shared with the right neighbour.

        The combined ``sdi_raw`` is then::

            numerator   = Σ_i [ inner_sdi_i × inner_area_i × weight_i ]
                        + Σ_adj [ shared_edge_sdi × f ]
            denominator = Σ_i [ inner_area_i × weight_i ]
                        + Σ_adj [ f ]

        where ``shared_edge_sdi`` is the average of the two adjacent edge-strip
        SDIs, and ``billing_area`` has no shared edges (weight = billing_weight).

        The other metrics are combined as follows:

        - **zone_sdi**      – weighted average across all images.
        - **sdi_uniformity** – recomputed from all wall segments combined
                               (walls only; billing_area excluded).
        - **sdi_depth**     – weighted average across all images.

        Args:
            wall_results: Mapping of image key → ``WallShelfResult``.
                          Typically produced by calling
                          ``analyze_with_edges()`` for each available image.

        Returns:
            A combined ``ShelfMetrics`` instance.
        """
        if not wall_results:
            logger.warning("combine_multi_wall: no wall results supplied")
            return ShelfMetrics()

        if len(wall_results) == 1:
            return next(iter(wall_results.values())).metrics

        f = self._overlap_frac

        # Images that share their left / right edges with a neighbour.
        _has_left_share: set = {"centre_wall", "right_wall"}
        _has_right_share: set = {"left_wall", "centre_wall"}

        # ── Step 1: inner SDI and area for each image ─────────────────────
        inner_sdis: Dict[str, float] = {}
        inner_areas: Dict[str, float] = {}  # in weighted area units

        for key, wr in wall_results.items():
            fl = f if key in _has_left_share else 0.0
            fr = f if key in _has_right_share else 0.0
            inner_area_frac = max(1.0 - fl - fr, 1e-6)

            # Recover inner-region SDI from the full-image SDI.
            raw_inner = (
                wr.metrics.sdi_raw
                - fl * wr.edge_left_sdi
                - fr * wr.edge_right_sdi
            )
            raw_inner = max(raw_inner, 0.0)
            inner_sdi = raw_inner / inner_area_frac

            inner_sdis[key] = inner_sdi
            inner_areas[key] = inner_area_frac * wr.weight

        # ── Step 2: shared edge contributions ─────────────────────────────
        shared_numerator = 0.0
        shared_denominator = 0.0

        for left_key, right_key in WALL_ADJACENCY:
            if left_key in wall_results and right_key in wall_results:
                shared_sdi = (
                    wall_results[left_key].edge_right_sdi
                    + wall_results[right_key].edge_left_sdi
                ) / 2.0
                shared_numerator += shared_sdi * f
                shared_denominator += f
                logger.debug(
                    "Shared edge %s↔%s: sdi=%.4f", left_key, right_key, shared_sdi
                )

        # ── Step 3: combined sdi_raw ───────────────────────────────────────
        num = sum(inner_sdis[k] * inner_areas[k] for k in inner_sdis)
        den = sum(inner_areas.values())
        num += shared_numerator
        den += shared_denominator

        combined_sdi_raw = max(0.0, min(num / den if den > 0 else 0.0, 1.0))

        # ── Step 4: zone_sdi – weighted average ───────────────────────────
        total_weight = sum(wr.weight for wr in wall_results.values())
        combined_zone: Dict[str, float] = {z: 0.0 for z in ZONE_SPLITS}
        for wr in wall_results.values():
            for z in ZONE_SPLITS:
                combined_zone[z] += wr.metrics.zone_sdi.get(z, 0.0) * wr.weight
        combined_zone = {
            z: round(v / total_weight, 4) for z, v in combined_zone.items()
        }

        # ── Step 5: sdi_uniformity – from all wall segments combined ──────
        all_segments: List[float] = []
        for key, wr in wall_results.items():
            if key != "billing_area":
                all_segments.extend(wr.metrics.wall_segment_sdis)
        combined_uniformity = self._compute_uniformity(all_segments)

        # ── Step 6: sdi_depth – weighted average ──────────────────────────
        combined_depth = (
            sum(wr.metrics.sdi_depth * wr.weight for wr in wall_results.values())
            / total_weight
        ) if total_weight > 0 else 0.0

        result = ShelfMetrics(
            sdi_raw=round(combined_sdi_raw, 4),
            zone_sdi=combined_zone,
            sdi_uniformity=round(combined_uniformity, 4),
            sdi_depth=round(combined_depth, 4),
            wall_segment_sdis=all_segments,
            diagnostics={
                "mode": "multi_wall",
                "images_used": list(wall_results.keys()),
                "per_image_inner_sdi": {k: round(v, 4) for k, v in inner_sdis.items()},
                "per_image_sdi_raw": {
                    k: round(wr.metrics.sdi_raw, 4)
                    for k, wr in wall_results.items()
                },
                "shared_edge_contribution": round(shared_numerator, 4),
                "overlap_fraction": f,
                "billing_weight": self._billing_weight,
            },
        )

        logger.info(
            "combine_multi_wall → sdi_raw=%.3f, uniformity=%.3f, "
            "depth=%.3f (images=%s)",
            result.sdi_raw, result.sdi_uniformity, result.sdi_depth,
            list(wall_results.keys()),
        )
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(image: np.ndarray) -> None:
        """Ensure the image is a valid 3-channel BGR array."""
        if image is None:
            raise ValueError("Image is None")
        if not isinstance(image, np.ndarray):
            raise ValueError(
                f"Expected numpy.ndarray, got {type(image).__name__}"
            )
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(
                f"Expected 3-channel image (H, W, 3), got shape {image.shape}"
            )
        if image.size == 0:
            raise ValueError("Image array is empty")
