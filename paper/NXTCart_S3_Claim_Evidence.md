# Supplementary S3 — Claim-to-Evidence Checklist

Companion to `NXTCart_Manuscript.md`. Every substantive claim in the manuscript is listed with the
artifact that supports it. Repository revision: `28aa58d3ceff6a7d03a2d208d9d4065606af85f8`
(11 October 2026).

## Evidence classes

| Class | Meaning | What it can support |
|---|---|---|
| **S** — Source | A named file in the repository at the stated revision | That the code *is written* a certain way |
| **T** — Test | A named test, executed and passing in this pass | That the logic *behaves* a certain way on constructed inputs |
| **A** — Analytical | Arithmetic or a derivation from source constants | A bound or a consequence, not an observation |
| **P** — Publication | A cited source, under *its* conditions | Prior art, framing, a method's provenance |
| **D** — Developer-reported | A figure recorded in the project's own notes | Nothing, until re-measured under §VII |
| **M** — Measured | A measurement made on the actual cart | Accuracy, latency, resource and security claims |

**Class M is empty.** No row in this document is supported by class M evidence. That is the single
most important fact in this checklist.

A claim is **sound** when its class matches its strength: an "is implemented as" claim needs S;
a "behaves correctly when" claim needs S+T; a "cannot exceed / must lag by" claim needs A;
a "performs better / is accurate / is secure" claim needs M and currently must not be made.

---

## Part A — Implementation claims (classes S, T)

| # | Claim | §  | Evidence | Class | Sound? |
|---|---|---|---|---|---|
| I1 | The Pi owns both cameras, decoding, catalogue, ledger and checkout permission; the PC holds no cart state | IV-A | `raspberry_pi/.../core_logic.py`, `verification.py`, `catalog.py`; `pi_sensors.launch.py` launches 5 Pi nodes | S | ✅ |
| I2 | The PC imports nothing from the Pi package and vice versa; enforced, not conventional | IV-A, VI-F | `scripts/run_tests.py::source_checks` boundary check; executed → PASS | S+T | ✅ |
| I3 | Both copies of `smart_cart_interfaces` are byte-identical | IV-B | Same check; executed → PASS | S+T | ✅ |
| I4 | A barcode scan never starts inference | V-B | `vision_verify_node.py::scan` logs only; `test_burst_vision.py::test_scan_and_motion_alone_never_trigger_inference` | S+T | ✅ |
| I5 | `/cart/placement_settled` is the only inference trigger | IV-B, V-B | `vision_verify_node.py::settled` → `dispatch_bursts` is the sole `submit` path | S | ✅ |
| I6 | The frame ring is bounded to 120 frames / 4.0 s with strictly increasing source stamps per generation | V-A | `vision_verify_node.py::frame`, `prune_frames`; `test_duplicate_camera_stamp_rejected_and_memory_bounded` | S+T | ✅ |
| I7 | The burst is the complete window, with no decimation | V-B | `dispatch_bursts` list comprehension; `test_dense_burst_preserves_fast_drop_and_only_embeds_crops` asserts 17 samples | S+T | ✅ |
| I8 | Density (≥12) and gap (≤80 ms, **both edges**) admissibility; failure → `RETRY` | V-B | `dispatch_bursts` gap computation pads with `start` and `end`; `test_packet_loss_gap_never_silently_decimated` | S+T | ✅ |
| I9 | A missing pre-entry baseline returns `RETRY`, not a full-frame fallback | V-B | `dispatch_bursts`; `test_missing_baseline_is_retry_not_full_frame_fallback` | S+T | ✅ |
| I10 | The baseline is the **newest** frame at or before `t_s − 0.90 s`, within 150 ms | V-B | `bases[-1]` over a time-ordered deque | S | ✅ |
| I11 | Collection waits for post-event frames rather than snapshotting on the callback | V-B | `settled` stores a collection; `test_settlement_waits_for_post_impact_frames`, `test_wifi_delivery_late_but_within_grace_is_used` | S+T | ✅ |
| I12 | Full frames never reach the network | V-C | `burst.py::verify_burst` passes only `region.crops`; `test_empty_scene_never_calls_embedding_matcher`, `test_global_lighting_change_is_never_full_frame_embedding` | S+T | ✅ |
| I13 | Connected components are never merged | V-C | `burst.py::foreground` per-contour crops; `test_separate_hand_and_product_do_not_merge_into_full_scene` | S+T | ✅ |
| I14 | Global scene change, oversized box and >8 regions are refusals | V-C | `foreground` three return-reject paths; `test_global_lighting_change…`, `test_sub_800_pixel_noise_discarded` | S+T | ✅ |
| I15 | Removal crops come from the baseline image, not the emptied basket | V-C | `verify_burst` swaps arguments for `item_removed`; `test_removal_embeds_departing_product_not_empty_basket` | S+T | ✅ |
| I16 | The embedding is the 1280-D GAP output, L2-normalised; logits are not used | V-D | `local_matcher.py::MobileNetONNX` probes for a 1280-element output and fails startup otherwise | S | ✅ |
| I17 | Live preprocessing is identical to the offline database builder | V-D, VI-A | `MobileNetONNX.embed` vs `pc/ml/embedding_extractor.py::_preprocess_onnx`: same 224², BGR→RGB, /255, mean/std, NCHW | S | ✅ |
| I18 | Every region is scored against every registered SKU | V-E | `local_matcher.py::verify` ranks `for key in self.products`; `test_later_swap_vetoes_earlier_match_and_every_crop_is_evaluated` asserts both embeddings computed | S+T | ✅ |
| I19 | Approval requires target top-1 **and** cosine ≥ 0.72 **and** margin ≥ 0.04 **and** colour/size | V-E | `verify` MATCH branch; `test_target_top1_above_72_and_margin_04_passes`, `test_target_high_absolute_score_but_small_margin_rejected`, `test_equal_score_tie_never_passes` | S+T | ✅ |
| I20 | A confident alternate SKU anywhere in the burst vetoes every match | V-E | `pool = swaps or matches or failures`; `test_green_soap_swap_returns_interloper…`, `test_later_swap_vetoes_earlier_match…` | S+T | ✅ |
| I21 | Mass and image gates are independent; a camera `MATCH` cannot clear a mass `FAIL` | III-C, IV-D | `verification.py::Unit.status` conjunction; `test_weight_mismatch_is_not_hidden_by_later_camera_match` | S+T | ✅ |
| I22 | Two independent mass comparisons; the firmware verdict can veto but not rescue | V-F | `verification.py::weight` (`CHECKING`) + `arduino_verdict`; `test_arduino_failure_cannot_be_overwritten_by_later_pass`, `test_arduino_failure_before_sample_is_bound_to_physical_delta` | S+T | ✅ |
| I23 | Verdicts are bound to `(txn_id, attempt)`; a stale attempt cannot satisfy a new one | IV-C, V-I | `vision_verify_node.py::key`/`seen`/`remember`; `verification.py::vision` attempt check; `test_verdict_cannot_be_reused_for_another_same_sku_unit`, `test_wrong_sku_attempt_and_action_are_ignored` | S+T | ✅ |
| I24 | Cancelled, timed-out, restarted and duplicate transactions cannot publish late approvals | V-I | `request(cancel)`, `tick` deadline, `publish` done-check; `test_cancel_running_and_late_result_cannot_approve`, `test_completed_but_over_deadline_result_fails_closed`, `test_reordered_request_and_duplicate_settlement_do_not_repeat_job` | S+T | ✅ |
| I25 | A camera generation change invalidates all in-flight work and forces reconciliation | V-A, V-I | `frame` generation branch + `/cart/scene_anomaly`; `test_camera_restart_invalidates_pending_burst`, `test_pc_restart_generation_requires_reconciliation` | S+T | ✅ |
| I26 | Heartbeats tolerate camera age to 5.0 s without invalidating verified units | V-I | `tick` health block; `test_camera_health_tolerates_five_seconds_even_if_buffer_pruned`, `test_pc_reconnect_never_restores_trust_after_unobserved_window` | S+T | ✅ |
| I27 | Scans appear immediately and a flagged unit does not lock the scanner | IV-E | `core_logic.py::scan_cb` → `publish_cart_state`; `test_scan_appears_immediately_and_checkout_waits_for_both_gates`, `test_failed_weight_does_not_block_later_shopping` | S+T | ✅ |
| I28 | Overlapping unsettled placements are flagged ambiguous, never guessed | IV-F | `verification.py::scan` pending>1 branch; `test_overlapping_unsettled_scans_are_ambiguous_not_guessed` | S+T | ✅ |
| I29 | Unexplained mass latches a checkout block, cleared only by returning to accounted mass | IV-F | `verification.py::weight` unassigned branch + `unexpected_mass_restored`; `test_unscanned_mass_blocks_then_removal_restores_checkout` | S+T | ✅ |
| I30 | Selected removal requires both a matching negative mass step and matching removal identity | IV-C | `verification.py::remove`, `finish_removal`; `test_selected_removal_needs_weight_and_camera_identity`, `test_same_weight_wrong_removal_does_not_discount_selected_product` | S+T | ✅ |
| I31 | Restart fails every non-`VERIFIED` unit; no silent re-tare of a loaded cart | IV-C | `VerificationLedger.__init__` recovery loop; `test_restart_requires_empty_cart_reconciliation`, `test_loaded_startup_never_tares_away_unscanned_products` | S+T | ✅ |
| I32 | Checkout is gated by all nine conditions including aggregate mass reconciliation and revision match | IV-D | `verification.py::checkout_reason`; `core_logic.py::checkout_cb`; `test_server_rejects_stale_checkout_revision`, `test_pending_and_sensor_disconnect_never_produce_payment_quote` | S+T | ✅ |
| I33 | A code re-arms only after a continuously observed absence, never after an outage | VI-C | `scan_gate.py`; `test_disconnect_does_not_scan_still_visible_code_again`, `test_observed_absence_rearms_same_sku`, `test_gap_interrupts_absence_dwell` | S+T | ✅ |
| I34 | A diagnostics disk failure cannot change a decision | VI-D | `verify_burst` try/except around `debug_store.save`; `test_debug_disk_error_does_not_change_decision` | S+T | ✅ |
| I35 | Diagnostic retention deletes only the writer's own UUID-named directories | VI-D | `burst.py::DebugStore.save` regex + symlink and re-resolve guards; `test_debug_images_manifest_and_retention` (asserts an unrelated directory survives) | S+T | ✅ |
| I36 | Clock skew beyond the guard windows is rejected, not absorbed | VI-E | `settled` age check, `frame` age check; `test_unknown_identity_and_stale_settlement_rejected` | S+T | ✅ |
| I37 | Start-up refuses internally inconsistent configuration | VI-B | `VisionNode.__init__` validation block | S | ✅ |
| I38 | Only `vision_verify_node` and `capture_references` are PC entry points; the motion/journey/geometric modules are not launched | VI-G | `pc/vision_ws/src/nxtcart_vision/setup.py`; `vision_verify_node.py` imports only `local_matcher` and `burst` | S | ✅ |
| I39 | Scanner-supplied price/name fields are not trusted | VI-A | `core_logic.py::scan_cb` uses `self.catalog.lookup`; `test_callbacks_bind_weight_camera_and_authoritative_price` | S+T | ✅ |
| I40 | The UPI QR is generated locally as a payment request, revision-gated | IV-D, IX-F | `gui_display.py` `upi://pay?` deep link; `core_logic.py::checkout_cb` revision check | S | ✅ |

## Part B — Analytical claims (class A)

| # | Claim | § | Derivation | Sound? |
|---|---|---|---|---|
| N1 | Frame ring ≈ 110.6 MB | V-A | 120 × 640 × 480 × 3 B, raw payload only | ✅ labelled analytical |
| N2 | Image topic ≈ 27.6 MB/s ≈ 221 Mb/s | V-A | 640 × 480 × 3 × 30 B/s, excludes DDS/IP/framing | ✅ labelled analytical |
| N3 | An admissible burst is normally 16–17 frames | V-B | 0.55 s window at the *requested* 30 FPS | ✅ labelled as expected, not observed |
| N4 | `Δ_stab ≈ 0.5–0.6 s` | V-G | `WINDOW=6` at ~100 ms gating ⇒ the 6th sample is ≥500 ms after the 1st | ✅ from firmware constants |
| N5 | **The configured burst cannot contain the descent** | V-G | `Δ_stab > δ_pre = 0.40 s`, so `Δ_s ≤ 0.40 s` is unsatisfiable | ✅ strongest analytical result |
| N6 | The baseline is pre-entry only while `Δ_s < 0.90 s` | V-G | Baseline at `t_s − δ_base`; contaminated once `t_s − 0.90 > t_0` | ✅ |
| N7 | Operating band `0.40 s < Δ_s < 0.90 s`, leaving 0.30–0.40 s decay budget | V-G | N4 ∧ N5 ∧ N6 | ✅ |
| N8 | Baseline contamination manifests as `MISMATCH`/`NO_ITEM_SEEN`, not a timeout | V-G, V-H | Empty mask ⇒ zero regions ⇒ `verify_burst` `if not count` branch | ✅ S+A |
| N9 | A 15 FPS camera fails the density test rather than degrading silently | VI-B | 0.55 s × 15 ≈ 8 frames < `n_min = 12` | ✅ |
| N10 | Ring is exactly sized: `120 = 4.0 s × 30 FPS`, and `4.0 > 0.90 + 0.15 + 0.75` | VI-B | Arithmetic against the start-up validation | ✅ |
| N11 | 16–17 near-duplicate frames carry ≈ one burst of independent information | V-G, VII-F | Consequence of N5 (static scene) | ✅ stated as a consequence |
| N12 | 30 trials with 0 failures ⇒ ≈9.5 % one-sided 95 % upper bound | VII-D | Clopper–Pearson | ✅ |
| N13 | Two conjunctive gates multiply false-reject rates, so B3 ≥ B1, B2 in retry rate | VIII-C | Structural, stated as an expectation to be measured | ✅ labelled expectation |

## Part C — Novelty and positioning claims (class P)

Each row states what is **not** claimed, what **is** claimed, and the prior art that forces the
distinction.

| # | Claim | § | Prior art that constrains it | Sound? |
|---|---|---|---|---|
| V1 | The barcode + weight + image **combination** is **not** claimed novel | I-B | [6] (2018 barcode+weight+images), [7] (2013 load cell + image comparison), [26] (2024 design), [27] (2026) | ✅ explicit disclaimer |
| V2 | **Weight reconciliation** is **not** claimed novel | I-B, II-B | [8] contributes exactly this, with measurements | ✅ |
| V3 | **Weight-triggered visual inference** is **not** claimed novel | I-B, II-C | [9] already triggers detection on a stabilised weight change | ✅ — the sharpest disclaimer; the catalogue's own guidance demanded it |
| V4 | **Crop → frozen embedding → nearest reference** is **not** claimed novel | I-B, II-D | [10] does exactly this, better, with no retraining; [11] compares verification formulations | ✅ |
| V5 | An unscanned-addition checkout block is **not** claimed novel | II-C | [25]'s "Unknown item" state blocks checkout identically | ✅ |
| V6 | **Retrospective** selection of a dense, gap-checked window from history (as opposed to starting a capture) is offered as a **design choice** | I-D(2), VIII-C | No located prior art does this; stated as a design choice, not a proven improvement | ✅ hedged correctly |
| V7 | Foreground-only, never-full-frame inference with explicit refusals is a **design choice** | I-D(3) | [9] embeds detector outputs; no located cart work restricts to pre-entry-baseline differences | ✅ hedged |
| V8 | All-SKU competition with a **burst-level veto** is a **hypothesis** | I-D(4) | [9] fuses; [10] identifies open-set; no located work vetoes across a burst | ✅ hedged; effectiveness is `[TO BE MEASURED]` |
| V9 | **Non-fused, conjunctive** gates are a deliberate contrast to fusion | I-D(5), II-C | [9] is decision-level fusion; [43], [44] frame fusion generally but do not establish channel independence | ✅ |
| V10 | The settlement-timing analysis is **analytical**, and is this paper's substantive result | I-D(6), V-G | No prior art needed; derived from own firmware | ✅ class A, correctly labelled |
| V11 | Object-category recognition, branded-SKU identification and verification-against-expectation are three distinct tasks | II-D | [24] vs [10],[31],[32],[37] vs [3],[11] | ✅ |
| V12 | An RFID payment wallet is not a per-product tag | II-A | [18]'s own design | ✅ — avoids the misrepresentation the audit warned about |
| V13 | Abstention must be characterised by risk against coverage, not accuracy | III-C, VII-E | [14] selective classification, [45] calibration | ✅ |

## Part D — Claims deliberately **not** made

The absence of these is itself a deliverable. Each is a claim the evidence would not support.

| # | Claim avoided | Why it cannot be made | Where the limit is stated |
|---|---|---|---|
| X1 | Any accuracy, FAR, FRR, detection-rate or latency figure for NXTCart | No class M evidence exists | Document Status, VIII-A, IX-A |
| X2 | "Prevents theft" / "prevents item switching" | A single camera cannot certify an occluded exchange; S16 is out of scope | IX-B; contrast with [26]'s unevaluated assertion |
| X3 | "Redundant sensing" for the two mass checks | Both read the same cell through the same HX711 | IX-C |
| X4 | Any statement about physical product size | Uncalibrated monocular aspect ratio only | V-D, IX-D |
| X5 | "Continuous scan-to-rest custody tracking" | No tracker in the live path; that was the retired pipeline | VI-G |
| X6 | "Full-frame embedding matching", "five-frame sampling", "JPEG transport", "live API inference" | All belong to retired versions | VI-G, S2 §E |
| X7 | Confirmed payment / settlement | A UPI deep-link QR is a request; no provider webhook exists | IV-D, IX-F |
| X8 | Any security guarantee | DDS security is not enabled; binding gives replay but not authentication resistance | IX-F |
| X9 | Light curtains, multiple cells, IMU compensation, navigation, inventory forecasting as features | Documented as planned design only in the project's own material | III-E R12, X |
| X10 | Shrinkage or loss-reduction impact | Depends on shopper behaviour, process and deterrence; not inferable from a bench matrix | IX-K |
| X11 | A systematic literature review | No registered protocol, date range, screening log or saturation search | IX-L, S1 |
| X12 | That another paper's accuracy is comparable to NXTCart's | Task, class count, split, event definition and hardware all differ | II-G caption, S2 §G |
| X13 | Market size or shrinkage statistics | No verified source; the catalogue's guidance forbids unsupported market claims | Absent throughout |
| X14 | That the software suites validate hardware, DDS or recognition | Stubs and constructed inputs only | VIII-B |
| X15 | The developer-reported 6.5 ms / leave-one-out figures as results | Undocumented protocol, *n* = 20, not the burst pipeline | S2 §H |
| X16 | Venue acceptance, peer review or deployment | None has occurred | Document Status |

## Part E — Results claims (class T — the only completed measurements)

| # | Claim | Evidence | Sound? |
|---|---|---|---|
| R1 | Software checks pass at revision `28aa58d`: 85 sources parsed, interface parity, boundary check, 103 + 4 tests, scripted suite | `python scripts/run_tests.py` executed in this pass on Windows 11 / Python 3.14.7 / OpenCV 5.0.0 / NumPy 2.5.2 | ✅ executed and reported with its environment |
| R2 | 35 of the 103 tests exercise the current burst pipeline; 12 target retired components | Enumerated from `tests/test_burst_vision.py`, `test_full_frame_vision.py::MotionTests`, `test_tracking_calibration.py`, `test_system.py::JourneyTests` | ✅ |
| R3 | These results establish nothing about DDS, frame rate, recognition accuracy, mass accuracy, `Δ_s`, native builds or security | Stated explicitly | ✅ |
| R4 | The authoring environment's OpenCV 5.0.0 exceeds the project's pinned `>=4.10,<5` | `pc/requirements.txt` vs the measured version | ✅ disclosed |
| R5 | `colcon` and the Arduino toolchain were absent, so native builds remain pending | Checked in this pass | ✅ disclosed |
| R6 | LaTeX compilation was **not** verified | No `pdflatex`/`xelatex`/`lualatex`/`latexmk` on the host | ✅ disclosed in the `.tex` header and S2 A7 |

---

## Consistency audit performed before delivery

| Check | Result |
|---|---|
| Architecture described matches the launched source and configuration | ✅ Resolved via `verification.yaml` + both launch files + the three live PC modules; the README/setup-guide supersession chain was followed, not trusted |
| All 24 config values in TABLE VI match `pc/config/verification.yaml` | ✅ Verified line by line |
| Firmware constants match `cart_scale.ino` | ✅ Verified |
| Obsolete descriptions excluded (full-frame, five-frame, JPEG, API, custody tracking, geometric zones) | ✅ None present; §VI-G names them as retired |
| Table numbering I–XI sequential, no duplicates, all in-text references updated | ✅ Verified by grep after renumbering |
| Figure numbering 1–6 sequential; every figure has a caption and a diagram specification | ✅ |
| Equation numbering (1)–(29) sequential; proposed equations separated as P1–P3 | ✅ |
| Algorithms 1–4 numbered; each maps to a named source function | ✅ |
| References: 56 entries, numbered by first appearance, no gaps, no duplicates | ✅ Verified programmatically |
| Every reference is cited in the text; every citation resolves to a reference | ✅ Verified programmatically |
| All 85 catalogue resources have exactly one disposition | ✅ Generator reports 56 cited + 29 excluded = 85, no ref missing |
| Deduplication by DOI, IEEE ID and title | ✅ No duplicates among the 85 |
| No invented results, dataset sizes, participant counts, accuracy, latency, cost, power or calibration values | ✅ Part D |
| Third-party figures attributed and never reused as NXTCart's | ✅ S2 §G |
| Novelty claims hedged or disclaimed per located prior art | ✅ Part C |
| Pending measurements visibly marked and greppable | ✅ S2 |
