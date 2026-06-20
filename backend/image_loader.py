"""Image loading and preprocessing module for Kirana store underwriting.

Loads a mandatory set of five store-view images (front, billing_area,
left_wall, centre_wall, right_wall), validates their existence and
decodability, resizes to a max dimension, detects low-light conditions,
and applies corrective enhancements (gamma correction, CLAHE,
denoising).  Returns processed numpy arrays ready for downstream
detection and analysis.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_IMAGE_KEYS: Tuple[str, ...] = (
    "front",
    "billing_area",
    "left_wall",
    "centre_wall",
    "right_wall",
)
"""The five mandatory store-view image slots that every submission must fill."""

MAX_DIMENSION: int = 1280
"""Images are resized so the longest edge does not exceed this value."""

LOW_LIGHT_THRESHOLD: float = 80.0
"""Grayscale mean below this value triggers the low-light enhancement
pipeline (gamma correction → CLAHE → denoising)."""

DEFAULT_GAMMA: float = 1.5
"""Gamma value used for brightening low-light images."""

CLAHE_CLIP_LIMIT: float = 3.0
"""Contrast-limit for the CLAHE histogram equalisation step."""

CLAHE_TILE_SIZE: Tuple[int, int] = (8, 8)
"""Tile grid size for CLAHE."""

DENOISE_STRENGTH: int = 10
"""Filter strength parameter for ``cv2.fastNlMeansDenoisingColored``."""


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class LoadedImageSet:
    """Container returned by ``ImageLoader.load()``.

    Attributes:
        images:       Mapping from image key → processed numpy array (BGR).
        diagnostics:  Per-image diagnostic info (original size, brightness,
                      whether enhancement was applied, etc.).
        all_valid:    ``True`` only when every required image was loaded
                      and processed successfully.
    """

    images: Dict[str, np.ndarray] = field(default_factory=dict)
    diagnostics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    all_valid: bool = False


# ---------------------------------------------------------------------------
# ImageLoader
# ---------------------------------------------------------------------------

class ImageLoader:
    """Loads, validates, and preprocesses the five required store-view images.

    Usage::

        loader = ImageLoader(image_paths={
            "front":        "imgs/front.jpg",
            "billing_area": "imgs/billing.jpg",
            "left_wall":    "imgs/left_wall.jpg",
            "centre_wall":  "imgs/centre_wall.jpg",
            "right_wall":   "imgs/right_wall.jpg",
        })
        result = loader.load()
        assert result.all_valid
        front_img = result.images["front"]   # numpy BGR array

    Config overrides (passed via *config* dict):
        - ``max_dimension``       (int)   – default 1280
        - ``low_light_threshold`` (float) – default 80.0
        - ``gamma``               (float) – default 1.5
        - ``clahe_clip_limit``    (float) – default 3.0
        - ``denoise_strength``    (int)   – default 10
    """

    def __init__(
        self,
        image_paths: Dict[str, str],
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the loader with per-slot file paths.

        Args:
            image_paths: Mapping of image key → filesystem path.
                         Must contain all keys in ``REQUIRED_IMAGE_KEYS``.
            config:      Optional processing parameter overrides.

        Raises:
            ValueError: If any required image key is missing from
                        *image_paths*.
        """
        self._validate_keys(image_paths)
        self.image_paths = image_paths
        self.config: Dict[str, Any] = config or {}

        # Resolve tuneable parameters.
        self._max_dim: int = int(
            self.config.get("max_dimension", MAX_DIMENSION)
        )
        self._low_light_thresh: float = float(
            self.config.get("low_light_threshold", LOW_LIGHT_THRESHOLD)
        )
        self._gamma: float = float(
            self.config.get("gamma", DEFAULT_GAMMA)
        )
        self._clahe_clip: float = float(
            self.config.get("clahe_clip_limit", CLAHE_CLIP_LIMIT)
        )
        self._denoise_str: int = int(
            self.config.get("denoise_strength", DENOISE_STRENGTH)
        )

        logger.info(
            "ImageLoader initialised – max_dim=%d, low_light_thresh=%.1f",
            self._max_dim,
            self._low_light_thresh,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> LoadedImageSet:
        """Load, validate, and preprocess all required images.

        Processing pipeline per image:
            1. Read from disk via OpenCV.
            2. Validate that decoding succeeded.
            3. Resize so the longest edge ≤ ``max_dimension``.
            4. Detect low-light via grayscale mean.
            5. If low-light → apply gamma correction, CLAHE, denoising.
            6. Run blur validation and genuine angle grid checks.

        Returns:
            A ``LoadedImageSet`` with processed arrays and diagnostics.
        """
        result = LoadedImageSet()
        all_ok = True

        # Step 0 - Compute file hashes to find duplicates
        hashes: Dict[str, str] = {}
        duplicates: Dict[str, str] = {}  # maps image_key -> other_image_key
        for key in REQUIRED_IMAGE_KEYS:
            path = self.image_paths[key]
            h = self._compute_file_hash(path)
            if h:
                if h in hashes:
                    duplicates[key] = hashes[h]
                else:
                    hashes[h] = key

        for key in REQUIRED_IMAGE_KEYS:
            path = self.image_paths[key]
            diag: Dict[str, Any] = {"path": path}

            if key in duplicates:
                diag["duplicate_of"] = duplicates[key]

            # Step 1 – Read.
            img = self._read_image(path)
            if img is None:
                diag["error"] = "Failed to read or decode image"
                result.diagnostics[key] = diag
                all_ok = False
                logger.error("Failed to load image [%s]: %s", key, path)
                continue

            diag["original_shape"] = img.shape  # (H, W, C)

            # Step 2 – Resize.
            img = self._resize(img)
            diag["resized_shape"] = img.shape

            # Step 3 – Low-light detection.
            brightness = self._compute_brightness(img)
            diag["brightness_mean"] = round(float(brightness), 2)
            is_low_light = brightness < self._low_light_thresh
            diag["low_light"] = is_low_light

            # Step 4 – Enhancement (conditional).
            if is_low_light:
                logger.info(
                    "Low-light detected for [%s] (mean=%.1f) – enhancing",
                    key,
                    brightness,
                )
                img = self._enhance(img)
                diag["enhanced"] = True
                diag["brightness_after"] = round(
                    float(self._compute_brightness(img)), 2
                )
            else:
                diag["enhanced"] = False

            # Step 5 - Quality & Blurriness Check
            blur_val = self._compute_blur_variance(img)
            diag["blur_variance"] = round(blur_val, 2)
            diag["is_blurry"] = blur_val < 80.0

            # Step 6 - Genuine Angle Grid Verification (for left, centre, right walls)
            angle_res = self._verify_shelf_grid(img, key)
            diag["genuine_angle_check"] = angle_res

            result.images[key] = img
            result.diagnostics[key] = diag
            logger.debug("Loaded [%s]: %s", key, diag)

        result.all_valid = all_ok
        logger.info(
            "ImageLoader.load() complete – all_valid=%s (%d/%d)",
            result.all_valid,
            len(result.images),
            len(REQUIRED_IMAGE_KEYS),
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_keys(image_paths: Dict[str, str]) -> None:
        """Ensure all required keys are present and paths are non-empty."""
        missing = [k for k in REQUIRED_IMAGE_KEYS if k not in image_paths]
        if missing:
            raise ValueError(
                f"Missing required image keys: {', '.join(missing)}. "
                f"Expected all of: {REQUIRED_IMAGE_KEYS}"
            )
        empty = [k for k in REQUIRED_IMAGE_KEYS if not image_paths[k].strip()]
        if empty:
            raise ValueError(
                f"Empty path(s) for image key(s): {', '.join(empty)}"
            )

    @staticmethod
    def _read_image(path: str) -> Optional[np.ndarray]:
        """Read an image from disk.

        Args:
            path: Absolute or relative filesystem path.

        Returns:
            BGR numpy array, or ``None`` on failure.
        """
        if not os.path.isfile(path):
            logger.warning("File does not exist: %s", path)
            return None

        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            logger.warning("cv2.imread returned empty for: %s", path)
            return None

        return img

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """Resize so the longest edge ≤ ``self._max_dim``.

        Aspect ratio is preserved.  Images already within limits are
        returned unchanged.
        """
        h, w = img.shape[:2]
        longest = max(h, w)

        if longest <= self._max_dim:
            return img

        scale = self._max_dim / longest
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        logger.debug("Resized %dx%d → %dx%d", w, h, new_w, new_h)
        return resized

    @staticmethod
    def _compute_brightness(img: np.ndarray) -> float:
        """Return the mean pixel intensity of the grayscale version."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def _enhance(self, img: np.ndarray) -> np.ndarray:
        """Apply the full low-light enhancement pipeline.

        Steps:
            1. Gamma correction (brightens dark regions non-linearly).
            2. CLAHE on the L channel of LAB colour space.
            3. Colour denoising to reduce noise amplified by steps 1-2.
        """
        img = self._apply_gamma(img, self._gamma)
        img = self._apply_clahe(img, self._clahe_clip)
        img = self._apply_denoise(img, self._denoise_str)
        return img

    @staticmethod
    def _apply_gamma(img: np.ndarray, gamma: float) -> np.ndarray:
        """Apply gamma correction.

        A gamma > 1 brightens the image; < 1 darkens it.
        """
        inv_gamma = 1.0 / gamma
        # Build a lookup table for speed.
        table = np.array(
            [((i / 255.0) ** inv_gamma) * 255 for i in range(256)],
            dtype=np.uint8,
        )
        return cv2.LUT(img, table)

    @staticmethod
    def _apply_clahe(img: np.ndarray, clip_limit: float) -> np.ndarray:
        """Apply CLAHE on the L channel of the LAB colour space."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=clip_limit, tileGridSize=CLAHE_TILE_SIZE
        )
        l_ch = clahe.apply(l_ch)

        merged = cv2.merge([l_ch, a_ch, b_ch])
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    @staticmethod
    def _apply_denoise(img: np.ndarray, strength: int) -> np.ndarray:
        """Apply fast non-local-means denoising for colour images."""
        return cv2.fastNlMeansDenoisingColored(
            img,
            None,
            h=strength,
            hColor=strength,
            templateWindowSize=7,
            searchWindowSize=21,
        )

    @staticmethod
    def _compute_file_hash(path: str) -> Optional[str]:
        """Compute MD5 checksum of a file to check for duplicates."""
        import hashlib
        if not os.path.isfile(path):
            return None
        hasher = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    @staticmethod
    def _compute_blur_variance(img: np.ndarray) -> float:
        """Compute the Laplacian variance to estimate image blurriness."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _verify_shelf_grid(image: np.ndarray, key: str) -> Dict[str, Any]:
        """Verify if the image exhibits the parallel line structural grid typical of store shelves."""
        if key not in ("left_wall", "centre_wall", "right_wall"):
            return {"is_genuine_angle": True, "details": "Not a shelf wall"}

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Hough Line Transform (HoughLinesP detects line segments)
        # minLineLength=100 ensures we detect long structural shelves, not tiny gaps
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
        
        horiz_count = 0
        slanted_count = 0
        total_lines = 0
        
        if lines is not None:
            total_lines = len(lines)
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = x2 - x1
                dy = y2 - y1
                
                if dx == 0:
                    continue  # Vertical lines
                
                slope = dy / dx
                angle_deg = np.arctan(slope) * 180 / np.pi
                
                # Almost horizontal (shelves from front-view)
                if abs(angle_deg) < 10.0:
                    horiz_count += 1
                # Slanted shelves (left/right walls)
                elif 10.0 <= abs(angle_deg) <= 35.0:
                    slanted_count += 1
        
        # We expect at least 3 prominent horizontal or slanted shelf lines
        # Given the 1280px downscaled image, this is highly reliable for identifying shelves.
        is_genuine = (horiz_count + slanted_count) >= 3
        
        return {
            "is_genuine_angle": is_genuine,
            "horizontal_line_count": horiz_count,
            "slanted_line_count": slanted_count,
            "total_lines": total_lines,
            "details": f"Detected {horiz_count} horizontal & {slanted_count} slanted structural shelf lines."
        }

