"""Object detection module for Kirana store underwriting.

Wraps an Ultralytics YOLO model behind a clean ``YOLODetector`` interface.
Each detection is returned as a ``Detection`` dataclass containing the
class name, confidence, bounding box, and the fraction of image area
the detection occupies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detection container
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """A single object detection result.

    Attributes:
        class_name:    Human-readable class label (e.g. ``"bottle"``).
        confidence:    Model confidence score (0.0 – 1.0).
        bbox:          Bounding box as ``(x1, y1, x2, y2)`` in pixels.
        area_fraction: Fraction of total image area covered by this box.
    """

    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]
    area_fraction: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": [round(v, 1) for v in self.bbox],
            "area_fraction": round(self.area_fraction, 6),
        }


# ---------------------------------------------------------------------------
# YOLODetector
# ---------------------------------------------------------------------------

class YOLODetector:
    """YOLO-based object detector for store images.

    Usage::

        detector = YOLODetector("yolov8n.pt")
        detections = detector.detect(image_bgr)
        for det in detections:
            print(det.class_name, det.confidence, det.bbox)

    Config overrides (via *config* dict):
        - ``confidence_threshold`` (float) – min confidence, default 0.25
        - ``device``               (str)   – ``"cpu"``, ``"cuda"``, etc.
        - ``imgsz``                (int)   – inference size, default 640
        - ``max_detections``       (int)   – cap results, default 300
    """

    DEFAULT_CONF_THRESHOLD: float = 0.25

    def __init__(
        self,
        model_path: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the detector and load the YOLO model.

        Args:
            model_path: Path to a ``.pt`` weights file **or** a model
                        name recognised by Ultralytics (e.g. ``"yolov8n.pt"``).
            config:     Optional parameter overrides.

        Raises:
            FileNotFoundError: If *model_path* cannot be resolved.
            RuntimeError:      If the model fails to load.
        """
        self.model_path = model_path
        self.config: Dict[str, Any] = config or {}

        self._conf_thresh: float = float(
            self.config.get("confidence_threshold", self.DEFAULT_CONF_THRESHOLD)
        )
        self._device: str = self.config.get("device", "cpu")
        self._imgsz: int = int(self.config.get("imgsz", 640))
        self._max_det: int = int(self.config.get("max_detections", 300))

        logger.info(
            "Loading YOLO model from '%s' (device=%s, conf=%.2f)",
            model_path,
            self._device,
            self._conf_thresh,
        )
        self._model = YOLO(model_path)
        logger.info("YOLO model loaded successfully")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, image: np.ndarray) -> List[Detection]:
        """Run detection on a single BGR image.

        Args:
            image: A numpy array of shape ``(H, W, 3)`` in BGR order
                   (the standard OpenCV convention).

        Returns:
            A list of ``Detection`` objects sorted by descending
            confidence.  Only detections meeting the confidence
            threshold are included.

        Raises:
            ValueError: If *image* is ``None`` or has an unexpected shape.
        """
        self._validate_image(image)

        img_h, img_w = image.shape[:2]
        img_area = float(img_h * img_w)

        results = self._model.predict(
            source=image,
            conf=self._conf_thresh,
            device=self._device,
            imgsz=self._imgsz,
            max_det=self._max_det,
            verbose=False,
        )

        detections = self._parse_results(results, img_area)

        logger.info(
            "Detected %d object(s) above conf=%.2f in %dx%d image",
            len(detections),
            self._conf_thresh,
            img_w,
            img_h,
        )
        return detections

    def detect_batch(self, images: List[np.ndarray]) -> List[List[Detection]]:
        """Run detection on a batch of images.

        Args:
            images: List of BGR numpy arrays.

        Returns:
            A list of detection lists, one per input image.
        """
        if not images:
            return []
        return [self.detect(img) for img in images]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_results(
        self, results, img_area: float
    ) -> List[Detection]:
        """Convert Ultralytics ``Results`` objects to ``Detection`` list."""
        detections: List[Detection] = []

        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                conf = float(boxes.conf[i])
                if conf < self._conf_thresh:
                    continue

                cls_id = int(boxes.cls[i])
                class_name = result.names.get(cls_id, f"class_{cls_id}")

                # xyxy format: (x1, y1, x2, y2)
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                bbox = (x1, y1, x2, y2)

                box_area = max(0.0, (x2 - x1) * (y2 - y1))
                area_fraction = box_area / img_area if img_area > 0 else 0.0

                detections.append(
                    Detection(
                        class_name=class_name,
                        confidence=conf,
                        bbox=bbox,
                        area_fraction=area_fraction,
                    )
                )

        # Sort by confidence descending.
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    @staticmethod
    def _validate_image(image: np.ndarray) -> None:
        """Raise ``ValueError`` if the image is unusable."""
        if image is None:
            raise ValueError("Image is None")
        if not isinstance(image, np.ndarray):
            raise ValueError(
                f"Expected numpy.ndarray, got {type(image).__name__}"
            )
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(
                f"Expected a 3-channel image (H, W, 3), "
                f"got shape {image.shape}"
            )
        if image.size == 0:
            raise ValueError("Image array is empty")
