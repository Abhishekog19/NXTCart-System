"""MobileNetV2 ONNX embeddings with optional colour and apparent-size evidence."""
from dataclasses import dataclass, field
import math
import json
import pickle
from pathlib import Path
import cv2
import numpy as np
from ml.verifier import colour_hist


def normalized(vector, dimension=1280):
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(value))
    if value.size != dimension or not np.isfinite(value).all() or not math.isfinite(norm) or norm < 1e-8:
        raise ValueError(f'Expected a finite, nonzero {dimension}-dimension vector')
    return value / norm


class MobileNetONNX:
    def __init__(self, path, layer=''):
        if not Path(path).is_file():
            raise FileNotFoundError(f'MobileNetV2 model missing: {path}')
        # OpenCV 4 (Jazzy) exposes pooled intermediate outputs directly. The
        # optional classic engine preserves this on development OpenCV 5 too.
        engine = getattr(cv2.dnn, 'ENGINE_CLASSIC', None)
        self.net = (cv2.dnn.readNetFromONNX(str(path), engine) if engine is not None
                    else cv2.dnn.readNetFromONNX(str(path)))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        probe = np.zeros((1, 3, 224, 224), np.float32)
        names = list(self.net.getLayerNames())
        likely = [n for n in names if any(h in n.lower() for h in ('pool', 'gap'))]
        candidates = [layer] if layer else list(dict.fromkeys(
            list(self.net.getUnconnectedOutLayersNames()) + likely + list(reversed(names))))
        self.layer = None
        for candidate in candidates:
            try:
                self.net.setInput(probe)
                output = self.net.forward(candidate)
                if output.size == 1280:
                    self.layer = candidate
                    break
            except cv2.error:
                continue
        if self.layer is None:
            raise ValueError('No 1280-D pooling output found; specify embedding_layer or use MobileNetV2')

    def embed(self, crop):
        # Match the existing build_db.py ONNX preprocessing exactly. Classifier
        # logits (usually 1000-D) are NOT the reference embedding space.
        rgb = cv2.cvtColor(cv2.resize(crop, (224, 224)), cv2.COLOR_BGR2RGB)
        value = rgb.astype(np.float32)/255.
        value = (value-np.array([.485, .456, .406], np.float32))/np.array([.229, .224, .225], np.float32)
        blob = np.ascontiguousarray(value.transpose(2, 0, 1)[None], dtype=np.float32)
        self.net.setInput(blob)
        return normalized(self.net.forward(self.layer))


@dataclass
class Result:
    verdict: str
    sku: str = ''
    score: float = 0.
    colour: float = 0.
    reason: str = ''
    code: str = ''
    evaluations: list = field(default_factory=list)


class LocalMatcher:
    def __init__(self, model_path, database_path, catalog_path='', threshold=.72,
                 colour_threshold=.30, size_ratio_tolerance=3., removal_margin=.04,
                 embedding_layer='', embedder=None, competitive_margin=.04, swap_threshold=.70):
        if not all(math.isfinite(x) for x in (threshold, colour_threshold, size_ratio_tolerance, removal_margin, competitive_margin, swap_threshold)):
            raise ValueError('All matcher thresholds must be finite')
        if not 0 <= competitive_margin <= 1 or not 0 < swap_threshold <= 1:
            raise ValueError('Invalid competitive margin or swap threshold')
        self.competitive_margin, self.swap_threshold = competitive_margin, swap_threshold
        if not 0 < threshold <= 1 or not 0 <= colour_threshold <= 1 or size_ratio_tolerance < 1 or not 0 <= removal_margin <= 1:
            raise ValueError('Invalid similarity, colour, size or removal-margin threshold')
        self.threshold, self.colour_threshold = threshold, colour_threshold
        self.size_tolerance, self.removal_margin = size_ratio_tolerance, removal_margin
        # This is a local, trusted database. Never load an untrusted pickle.
        with Path(database_path).expanduser().open('rb') as handle:
            raw = pickle.load(handle)
        if not isinstance(raw, dict) or not raw:
            raise ValueError('Embedding database must be a nonempty dictionary')
        wrapped = isinstance(raw.get('products'), dict)
        if wrapped and raw.get('backend', 'onnx-mbv2-1280') != 'onnx-mbv2-1280':
            raise ValueError('Database is not ONNX MobileNetV2; rebuild with the same model/preprocessing')
        if wrapped and raw.get('dim', 1280) != 1280:
            raise ValueError('Database embedding dimension must be 1280')
        products = raw['products'] if wrapped else raw
        self.products, self.aliases = {}, {}
        for sku, value in products.items():
            meta = value if isinstance(value, dict) else {'embeddings': value}
            vectors = np.asarray(meta.get('embeddings', []), dtype=np.float32)
            if vectors.ndim == 1:
                vectors = vectors[None, :]
            if vectors.ndim != 2 or not len(vectors):
                raise ValueError(f'{sku}: embeddings must contain one or more 1280-D vectors')
            embeddings = np.stack([normalized(v) for v in vectors])
            colours = meta.get('color_histograms', meta.get('colours', meta.get('colors',
                raw.get('colours', {}).get(sku, []) if wrapped else [])))
            if colours is None:
                colours = []
            colour_vectors = np.asarray(colours, np.float32)
            if colour_vectors.size and colour_vectors.ndim == 1:
                colour_vectors = colour_vectors[None, :]
            if colour_vectors.size:
                if colour_vectors.ndim != 2 or colour_vectors.shape[1] != 80:
                    raise ValueError(f'{sku}: colour histograms must use the existing 80-bin format')
                if wrapped and raw.get('colour_format', 2) != 2:
                    raise ValueError('Unsupported colour format; rebuild with build_db.py')
                colour_vectors = np.stack([normalized(v, 80) for v in colour_vectors])
            expected_color = meta.get('expected_color_bgr', meta.get('expected_color'))
            if expected_color is not None:
                expected_color = np.asarray(expected_color, np.float32)
                if expected_color.shape != (3,) or not np.isfinite(expected_color).all() or not ((expected_color >= 0) & (expected_color <= 255)).all():
                    raise ValueError(f'{sku}: expected_color must be a BGR triple in 0..255')
            sizes = meta.get('sizes', meta.get('expected_size', raw.get('sizes', {}).get(sku, []) if wrapped else []))
            sizes = np.asarray(sizes, np.float32)
            ratios = []
            if sizes.size:
                sizes = sizes.reshape(-1, 2)
                if not np.isfinite(sizes).all() or np.any(sizes <= 0):
                    raise ValueError(f'{sku}: sizes must be positive [width,height] pixel pairs')
                ratios = np.max(sizes, axis=1)/np.min(sizes, axis=1)
            key = str(sku)
            self.products[key] = (embeddings, colour_vectors, expected_color, ratios)
            self.alias(key, key)
            for label in (meta.get('barcode'), meta.get('name')):
                if label:
                    self.alias(str(label), key)
        if not self.products:
            raise ValueError('Database has no products')
        if catalog_path:
            for row in json.loads(Path(catalog_path).expanduser().read_text(encoding='utf-8')):
                if row['sku'] in self.products:
                    self.alias(row['barcode'], row['sku'])
                    self.alias(row['name'], row['sku'])
        self.embedder = embedder or MobileNetONNX(Path(model_path).expanduser(), embedding_layer)

    @staticmethod
    def key(value):
        return str(value).strip().casefold().replace(' ', '_')

    def alias(self, label, sku):
        key = self.key(label)
        if key in self.aliases and self.aliases[key] != sku:
            raise ValueError(f'Conflicting catalogue alias: {label}')
        self.aliases[key] = sku

    def resolve(self, barcode, name=''):
        return self.aliases.get(self.key(barcode)) or self.aliases.get(self.key(name))

    def score(self, sku, crop, embedding):
        refs, colours, expected_color, ratios = self.products[sku]
        # Cosine similarity = dot(L2-normalized query, normalized reference).
        similarity = float(np.clip(np.max(refs @ embedding), -1., 1.))
        colour_score, colour_ok = 0., True
        if colours.size:
            observed = colour_hist(crop)
            norm = float(np.linalg.norm(observed))
            colour_score = float(np.clip(np.max(colours @ (observed/norm)), 0., 1.)) if norm > 1e-8 else 0.
            colour_ok = colour_score >= self.colour_threshold
        if expected_color is not None:
            mean = np.mean(crop.reshape(-1, 3), axis=0)
            bgr_score = float(1.-np.linalg.norm(mean-expected_color)/(255.*np.sqrt(3.)))
            colour_score = min(colour_score, bgr_score) if colours.size else bgr_score
            colour_ok = colour_ok and bgr_score >= self.colour_threshold
        aspect = max(crop.shape[:2])/min(crop.shape[:2])
        size_ok = not len(ratios) or any(max(aspect/r, r/aspect) <= self.size_tolerance for r in ratios)
        return similarity, colour_score, colour_ok and size_ok

    def verify(self, sku, samples):
        """Rank every catalog SKU for every foreground ROI, never full scenes.

        All crops are evaluated, including frames after the first match. A
        confident alternate product vetoes a target match elsewhere in the
        burst so a hand-held target cannot hide a different dropped product.
        """
        if sku and sku not in self.products:
            return Result('UNAVAILABLE', sku, reason='No reference embeddings for scanned barcode/SKU')
        evaluations, matches, swaps, failures = [], [], [], []
        for frame_index, sample in enumerate(samples):
            for crop_index, crop in enumerate(sample):
                entry = dict(frame_index=frame_index, crop_index=crop_index)
                try:
                    if crop is None or crop.ndim != 3 or crop.shape[2] != 3 or min(crop.shape[:2]) < 8:
                        raise ValueError('Invalid foreground ROI')
                    embedding = normalized(self.embedder.embed(crop))
                    ranked = sorted(((self.score(key, crop, embedding), key)
                                     for key in self.products), key=lambda row: (-row[0][0], row[1]))
                except (ValueError, cv2.error) as exc:
                    evaluations.append(dict(entry, verdict='UNAVAILABLE', error=str(exc)))
                    continue
                (score, colour, evidence_ok), key = ranked[0]
                runner = ranked[1][0][0] if len(ranked) > 1 else -1.
                target_score = next((row[0][0] for row in ranked if row[1] == sku), score)
                margin = score - runner
                required_margin = self.competitive_margin if sku else self.removal_margin
                if sku and key != sku and score >= self.swap_threshold:
                    result = Result('MISMATCH', key, score, colour,
                                    f'Product swap detected: observed {key} instead of {sku}', 'SWAP_DETECTED')
                    swaps.append(result)
                elif (not sku or key == sku) and score >= self.threshold and margin >= required_margin and evidence_ok:
                    result = Result('MATCH', key, score, colour,
                                    f'Target is top-1: cosine={score:.3f}, margin={margin:.3f}; colour/size passed', 'MATCH')
                    matches.append(result)
                else:
                    reason = (f'Embedding similarity below confidence threshold or competitive margin: '
                              f'top1={key}, score={score:.3f}, target={target_score:.3f}, '
                              f'margin={margin:.3f}, colour/size={evidence_ok}')
                    result = Result('MISMATCH', sku or key, score, colour, reason, 'LOW_CONFIDENCE')
                    failures.append(result)
                evaluations.append(dict(entry, top1=key, score=score, target_score=target_score,
                                        runner_up=ranked[1][1] if len(ranked) > 1 else '',
                                        runner_up_score=runner, margin=margin, colour=colour,
                                        evidence_ok=bool(evidence_ok), verdict=result.verdict,
                                        code=result.code))
        pool = swaps or matches or failures
        result = max(pool, key=lambda item: item.score) if pool else Result(
            'UNAVAILABLE', sku, reason='No valid foreground embeddings could be evaluated', code='NO_EMBEDDING')
        result.evaluations = evaluations
        return result
