"""Full-frame motion proposals; no zones, trajectories or merge failures."""
import cv2
import numpy as np


class MotionDetector:
    def __init__(self, min_area=100., warmup_frames=15, max_candidates=4):
        self.min_area, self.warmup_frames = min_area, warmup_frames
        self.max_candidates = max_candidates
        self.background = cv2.createBackgroundSubtractorMOG2(history=250, varThreshold=24, detectShadows=True)
        self.frames = 0
        self.boxes = []

    @property
    def ready(self):
        return self.frames >= self.warmup_frames

    def detect(self, frame):
        scale = min(1., 640./frame.shape[1])
        work = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
        mask = self.background.apply(work, learningRate=.01)
        self.frames += 1
        # MOG2 labels shadows 127. Keep foreground 255, never the shadow label.
        mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)[1]
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) >= self.min_area*scale*scale]
        self.boxes = [(int(x/scale), int(y/scale), int(w/scale), int(h/scale)) for x,y,w,h in boxes]
        if not self.ready or not self.boxes:
            return []
        # Hands or several foreground regions no longer trigger "Multiple moving
        # regions". Try colour-prominent individual crops and a merged crop.
        # We do not associate frames or compare growing areas: no MERGED state.
        height, width = frame.shape[:2]
        candidates = []
        for x,y,w,h in self.boxes:
            crop = frame[y:min(y+h,height), x:min(x+w,width)]
            saturation = float(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:,:,1].mean())
            candidates.append((saturation*np.sqrt(w*h), (x,y,w,h)))
        candidates.sort(reverse=True)
        selected = [b for _, b in candidates[:self.max_candidates-1]]
        left, top = min(b[0] for b in self.boxes), min(b[1] for b in self.boxes)
        right, bottom = max(b[0]+b[2] for b in self.boxes), max(b[1]+b[3] for b in self.boxes)
        selected.append((left, top, right-left, bottom-top))
        crops, seen = [], set()
        for x,y,w,h in selected:
            if (x,y,w,h) in seen:
                continue
            seen.add((x,y,w,h))
            pad = max(2, int(.04*max(w,h)))
            crop = frame[max(0,y-pad):min(height,y+h+pad), max(0,x-pad):min(width,x+w+pad)]
            # Keep fall blur; a later sharper frame may be the one that matches.
            if min(crop.shape[:2]) < 8:
                continue
            ratio = min(1., 320./max(crop.shape[:2]))
            crops.append(cv2.resize(crop, None, fx=ratio, fy=ratio).copy())
        return crops
