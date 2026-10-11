"""Pure image processing after a weight trigger; never embeds a full frame."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import shutil
import uuid
from pathlib import Path

import cv2
import numpy as np

from .local_matcher import Result


@dataclass
class Foreground:
    crops: list
    boxes: list
    rejected: str = ''


def foreground(baseline, frame, min_area=800., threshold=25, padding=.12,
               max_roi_fraction=.65):
    """Fixed pre-entry baseline differencing, NOT a background-subtractor trigger.

    Each connected component gets its own tight crop. Merging distant hands and
    products into a scene-sized rectangle would reintroduce background leakage.
    Global lighting changes/camera shifts are rejected instead of embedding them.
    """
    if baseline.shape != frame.shape:
        return Foreground([], [], 'Frame geometry changed')
    difference = cv2.absdiff(baseline, frame)
    # Maximum channel difference preserves changes in similarly bright colours.
    mask = (np.max(difference, axis=2) > threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    height, width = frame.shape[:2]
    if np.count_nonzero(mask) > height * width * max_roi_fraction:
        return Foreground([], [], 'Global scene change; foreground cannot be isolated')
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    crops, boxes = [], []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(contour) < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        px, py = max(1, round(w * padding)), max(1, round(h * padding))
        x0, y0, x1, y1 = max(0, x-px), max(0, y-py), min(width, x+w+px), min(height, y+h+py)
        if (x1-x0) * (y1-y0) > height * width * max_roi_fraction:
            return Foreground([], [], 'Foreground bounding box covers too much of the scene')
        boxes.append((x0, y0, x1-x0, y1-y0))
        crops.append(frame[y0:y1, x0:x1].copy())
    # Many disjoint changes usually indicate camera shake/noise, not one item.
    # Fail closed rather than silently discarding a possibly swapped product.
    if len(crops) > 8:
        return Foreground([], [], 'Too many changed regions to isolate a product')
    return Foreground(crops, boxes)


def token(value):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(value))[:64] or 'unknown'


class DebugStore:
    """Single-worker, bounded, best-effort diagnostic storage.

    Only directories created with our UUID prefix are eligible for retention
    cleanup; arbitrary files and symlinked directories are never followed.
    """
    def __init__(self, path, keep=100):
        self.path = Path(path).expanduser().resolve()
        self.keep = keep
        if keep < 1:
            raise ValueError('debug_keep must be positive')

    def save(self, capture, baseline, burst, regions, result, metadata):
        self.path.mkdir(parents=True, exist_ok=True)
        owned = sorted(p for p in self.path.iterdir() if p.is_dir() and not p.is_symlink()
                       and re.fullmatch(r'nxtcart_\d{8}T\d{12}Z_[0-9a-f]{32}', p.name))
        for old in owned[:max(0, len(owned)-self.keep+1)]:
            # Resolve again immediately before recursive deletion.
            if old.resolve().parent == self.path and not old.is_symlink():
                shutil.rmtree(old)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder = self.path / f'nxtcart_{stamp}_{uuid.uuid4().hex}'
        folder.mkdir()
        def write(name, image):
            if not cv2.imwrite(str(folder / name), image, [cv2.IMWRITE_JPEG_QUALITY, 90]):
                raise OSError(f'Could not write debug image {name}')

        write('baseline.jpg', baseline)
        for i, ((_, stamp_ns, frame), region) in enumerate(zip(burst, regions)):
            frame_scores = [e for e in result.evaluations if e['frame_index'] == i and 'top1' in e]
            top = max(frame_scores, key=lambda e: e['score']) if frame_scores else {}
            suffix = (f'{token(capture.sku)}_top-{token(top.get("top1", "none"))}_'
                      f'{top.get("score", 0.):.3f}_{token(result.verdict)}')
            write(f'{i:03d}_{stamp_ns}_full_{suffix}.jpg', frame)
            for j, crop in enumerate(region.crops):
                evaluation = next((e for e in result.evaluations
                                   if e['frame_index'] == i and e['crop_index'] == j), {})
                label = (f'{token(capture.sku)}_top-{token(evaluation.get("top1", "unscored"))}_'
                         f'{evaluation.get("score", 0.):.3f}_{token(evaluation.get("verdict", result.verdict))}')
                write(f'{i:03d}_roi-{j:02d}_{label}.jpg', crop)
        payload = dict(metadata, txn_id=capture.txn_id, scan_id=capture.scan_id,
                       attempt=capture.attempt, requested_sku=capture.sku,
                       decision=dict(verdict=result.verdict, code=result.code, sku=result.sku,
                                     score=result.score, reason=result.reason),
                       evaluations=result.evaluations,
                       frames=[dict(stamp_ns=f[1], boxes=r.boxes, rejected=r.rejected)
                               for f, r in zip(burst, regions)])
        (folder / 'manifest.json').write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')
        return str(folder)


@dataclass
class BurstOutcome:
    result: Result
    crop_count: int
    debug_path: str = ''
    debug_error: str = ''


def verify_burst(backend, capture, baseline, burst, segmentation, debug_store, metadata):
    """Runs only in the single ONNX worker. Full frames go only to debug storage."""
    # For a selected removal the departing product is in the baseline. Cropping
    # the now-empty basket would embed background and recreate the leakage bug.
    regions = [foreground(entry[2], baseline, **segmentation) if capture.action == 'item_removed'
               else foreground(baseline, entry[2], **segmentation) for entry in burst]
    samples = [region.crops for region in regions]
    count = sum(map(len, samples))
    if not count:
        result = Result('MISMATCH', capture.sku,
                        reason='No foreground product motion observed during placement window',
                        code='NO_ITEM_SEEN')
    elif any(region.rejected for region in regions):
        result = Result('RETRY', capture.sku, reason='Scene changed too much to isolate the product',
                        code='SCENE_CHANGED')
    else:
        try:
            result = backend.verify(capture.sku, samples)
        except Exception as exc:
            result = Result('UNAVAILABLE', capture.sku, reason=f'Image verification failed: {exc}',
                            code='INFERENCE_ERROR')
    outcome = BurstOutcome(result, count)
    try:
        outcome.debug_path = debug_store.save(capture, baseline, burst, regions, result, metadata)
    except (OSError, ValueError, cv2.error) as exc:
        # An unwritable diagnostics disk must not turn a mismatch into a match
        # or stop camera/heartbeat callbacks. Report the failure explicitly.
        outcome.debug_error = str(exc)
    return outcome
