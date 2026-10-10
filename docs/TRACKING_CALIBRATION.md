# Historical geometric tracker notes

This tracker is retired. The active full-frame node has no geometric boxes or
MERGED checks. Use [LENIENT_VISION_SETUP.md](LENIENT_VISION_SETUP.md).

# Reduce false tracking retries

`Multiple moving regions` and `MERGED` happen before product-reference inference.
Changing from local ML to a vision API alone will not correct these errors.
The current detector identifies moving silhouettes; it does not classify hands.

The tracker now compares actual foreground area instead of the empty corners
of an axis-aligned bounding box. This removes one cause of rotation-induced
`MERGED` errors. A hand joining the packet or the packet moving closer to the
camera can still enlarge the foreground; those events are not automatically safe.

## Calibrate the mounted camera

1. Fix the camera rigidly, with steady diffuse lighting and a clear view from
   the scan position to the complete basket. Keep the packet fully visible;
   holding an edge generally obstructs less packaging than covering its face.
2. Start with an empty, still basket so background warm-up can finish.
3. From the repository root on PC, run:

   ```bash
   bash pc/run_verifier.sh backend:=local preview:=true
   ```

4. The color view shows the scene boundary in blue, scan region in amber,
   rest region in green, foreground regions in cyan and the target in magenta.
   The second window shows the actual foreground mask. White means motion,
   not a recognized product. Check whether a second white region is a hand,
   another product, a reflection or background motion.
5. Edit `pc/config/verification.yaml`, then restart the PC node. Coordinates
   are fractions of image width/height: `[left, top, right, bottom]`.
   `scene_region` excludes unrelated background before detection; it must
   contain both scanner/cart regions and the full physical product journey.
   Never crop out the basket, an alternative entry path or the product merely
   to remove a warning. Motion outside the configured view cannot be monitored.
6. Repeat normal placements and deliberate wrong/equal-weight products. Keep
   the scale and camera gates enabled and record false accepts as well as retries.

For a separate calibration file:

```bash
bash pc/run_verifier.sh preview:=true config_file:=/absolute/path/verification.yaml
```

On failure the PC logs bounding boxes, foreground pixel areas and the measured
growth ratio. A `MERGED` message now says which area metric and ratio triggered
the guard. Do not simply raise `merge_area_ratio` or ignore all extra regions:
that also makes an additional product easier to overlook.

## When a hand and packet still merge

Camera geometry and foreground area do not solve hand/product segmentation.
If ordinary one-product placements keep failing with a correctly calibrated
view, the next detector needs explicit product and hand separation, trained and
validated on the mounted cart's footage. Record normal placements, hand overlap,
rotations, a partly filled basket, two-item insertions and equal-weight swaps.
Annotate visible product boundaries separately from hands, then evaluate the
detector through the existing `Detection(bbox, mask, quality)` interface.
General motion blobs or skin-color exclusion cannot establish product identity.

A fully obscured product, ambiguous two-product motion or missing camera frames
must still return an unresolved result. Neither these changes nor any single
camera can guarantee zero uncertainty. Review actual footage before changing
acceptance rules. The setup guide's hardware acceptance matrix remains required.
