# Settlement-Triggered, Foreground-Only Verification of Scanned Products in a Barcode-First Smart Shopping Cart: Prototype Architecture and Evaluation Protocol

**Authors:** [AUTHOR 1 NAME]¹, [AUTHOR 2 NAME]¹, [AUTHOR 3 NAME]¹, [AUTHOR 4 NAME]²

¹ [DEPARTMENT], [INSTITUTION], [CITY], [COUNTRY] — {[email1], [email2], [email3]}@[domain]
² [DEPARTMENT], [INSTITUTION], [CITY], [COUNTRY] — [email4]@[domain]

**Corresponding author:** [CORRESPONDING AUTHOR NAME] ([email]@[domain])

---

> **Document status.** This is a system-design and prototype manuscript. Every quantitative claim
> about recognition accuracy, latency, power, cost or theft coverage is marked
> `[TO BE MEASURED: …]` because the hardware acceptance campaign described in Section VII has not
> been executed. The only measurements reported as completed are the host-independent software
> checks in Section VIII-A, which the authors executed at the stated repository revision. Nothing in
> this manuscript should be read as implying venue acceptance, peer review, store deployment or
> completed field validation.

---

## Abstract

Self-checkout and smart-cart systems move the act of product identification from a trained cashier
to the shopper, which creates a verification problem: the store must establish that the physical
object placed in the basket is the object whose barcode was presented. Combining barcode, weight and
image evidence is long-established prior art, so this paper does not claim that combination as a
contribution. Instead we specify and document a prototype, **NXTCart**, whose distinguishing design
choices are mechanisms rather than modalities: (i) visual inference is neither continuous nor
scan-triggered but is launched retrospectively from a bounded, source-timestamped frame history when
the cart's load cell reports a *settled* mass change, so the evidence window is selected after the
physical event rather than guessed before it; (ii) only connected foreground regions obtained by
differencing against a *pre-entry* baseline frame are embedded, so no full scene — and therefore no
basket background — ever reaches the recognition network; (iii) each candidate region is scored
against **every** registered SKU rather than only the scanned one, and a sufficiently confident
alternate SKU anywhere in the burst **vetoes** a matching region elsewhere, so an early correct view
cannot outvote a later substituted product; (iv) every verdict is bound to a transaction and attempt
identifier, and the weight and image gates remain **independent and conjunctive** rather than fused
into a single score, so a visual match can never clear a mass failure. We give the complete runtime
contract: a Raspberry Pi owns both USB cameras, barcode decoding, the catalogue, the durable per-unit
ledger and checkout permission; an Arduino/HX711 performs calibrated acquisition, a six-sample
stability test and an independent transaction-specific expected-weight comparison; a PC runs
foreground segmentation and local MobileNetV2 ONNX embedding comparison over ROS 2. We contribute a
quantitative feasibility analysis showing that, with the shipped firmware constants, the settlement
timestamp necessarily lags mechanical impact by at least approximately 0.5 s, so the configured
window observes the product *at rest* rather than in descent, and that the configuration is only
self-consistent while the impact-to-settlement delay stays below 0.90 s — beyond which the selected
baseline becomes contaminated by the product itself. We provide a reproducible evaluation protocol
with baselines (barcode-only, barcode+weight, barcode+vision, full system), ablations of each
mechanism, an adversarial and nuisance scenario matrix, metric denominators and leakage controls.
Results are explicitly pending.

**Keywords:** smart shopping cart, product verification, barcode switching, weight reconciliation,
foreground segmentation, embedding similarity, event-triggered sensing, ROS 2, selective
classification, retail loss prevention

---

## I. Introduction

### A. Problem

Automated retail identification has been studied extensively from the perception side: surveys of
computer-vision approaches to in-store product identification [1] and of deep learning for retail
product recognition [2] document a large literature on detecting and classifying merchandise. A
smaller but more directly relevant line of work treats the task as *verification* rather than
*recognition* — deciding whether a presented object is consistent with a declared product identity,
explicitly motivated by barcode switching and missed scans at self-checkout [3]. Commercial
smart-cart products describe camera and weight checks on the cart itself [4], [5]; these are vendor
descriptions and are cited here only as deployment context, not as evidence of accuracy or loss
reduction.

The gap this paper addresses is not "can a cart see products". It is narrower and more mechanical:
**given that a shopper has scanned a barcode, which pixels constitute admissible evidence about the
object that just entered the basket, and what decision rule over those pixels is defensible when the
evidence may be incomplete?**

### B. Scope and what is not claimed

Carts that combine a barcode or RFID reader with a load cell and a camera are at least a decade old.
A 2018 barcode-first design already combined weight checks, product images and a cloud inventory
[6], and a 2013 wireless-sensor cart already combined a load cell with image comparison for billing
verification [7]. A 2026 cart paper contributes a load-cell weight-reconciliation algorithm with
tolerance windows and drift compensation and explicitly lists adding camera verification to
disambiguate equal-weight items as *future work* [8]. A 2025 cart fuses RGB-D vision, basket weight
and RFID at the decision level and already triggers full detection only when the weight sensor
reports a significant change [9]. Consequently this paper claims **neither** multimodal cart
verification, **nor** weight reconciliation, **nor** weight-triggered visual inference as novel.

Likewise, the visual method is deliberately conventional. Decoupling localisation from
classification and classifying by nearest-reference similarity in an embedding space — so that a new
SKU requires only new reference photographs and no retraining — is established retail practice
[10], and class-verification formulations for self-checkout products have been compared directly
[11]. We use an unmodified pretrained MobileNetV2 [12] as a frozen feature extractor and do not
claim a representation-learning contribution.

### C. Research question

> Does *transaction-bound* agreement between a scanned barcode, an independently checked settled mass
> change, and a foreground-only visual verification of the scanned SKU reduce accepted substitution
> and billing errors relative to barcode-only, barcode-plus-weight and barcode-plus-vision
> baselines, at an acceptable honest-shopper retry rate and end-to-end latency?

This is the question the protocol in Section VII is designed to answer. It is a framing, not a
result.

### D. Contributions

We claim the following, and we label each by the kind of evidence that currently supports it.

1. **A fully specified, source-verified runtime contract** for a three-host barcode-first
   verification cart on ROS 2 [13], including the exact topic graph, message schemas, quality-of-
   service settings, bounded buffers, timeout and cancellation semantics, durable per-unit state, and
   the checkout predicate. *Evidence: static inspection of the launched source at a recorded
   revision (Section VI).*
2. **Settlement-triggered retrospective evidence selection.** The PC maintains a bounded ring of
   source-timestamped frames and, on a settlement event, extracts the complete window
   `[t_settled − 0.40 s, t_settled + 0.15 s]` plus a pre-entry baseline at `t_settled − 0.90 s`,
   admitting the burst only if it is dense (≥ 12 frames) and gap-free (≤ 80 ms, including both
   window edges). Incomplete evidence returns `RETRY` rather than a decision. *Evidence: implemented
   and unit-tested; labelled a design choice, not a demonstrated improvement.*
3. **Foreground-only inference.** Full frames are never embedded. Only connected components of a
   baseline difference mask, individually cropped with 12 % padding, reach the network; global scene
   changes and scene-sized boxes are refused rather than embedded. *Evidence: implemented and
   unit-tested, including a regression test asserting that an empty scene and a global lighting
   change never invoke the matcher.*
4. **All-SKU competition with a burst-level substitution veto.** Every region is ranked against every
   registered SKU; approval requires the scanned SKU to be top-1 with cosine ≥ 0.72 and a competitor
   margin ≥ 0.04; an alternate SKU scoring ≥ 0.70 produces `MISMATCH`/`SWAP_DETECTED` and takes
   precedence over any matching region elsewhere in the same burst. *Evidence: implemented and
   unit-tested; its effectiveness against real lookalikes is* `[TO BE MEASURED]`.
5. **Independent, non-fused, conjunctive gates with transaction/attempt binding.** Unlike
   decision-level fusion designs [9], the mass and image decisions are never combined into a single
   score. A unit is billable only when both gates pass for the current attempt, and the Arduino's
   independent comparison can veto but never rescue the Pi's own comparison. *Evidence: implemented
   and unit-tested; motivated by selective-classification reasoning [14] rather than by measurement.*
6. **A quantitative settlement-timing feasibility analysis** (Section V-G) showing from the shipped
   firmware constants that the configured burst cannot contain the descent, that the configuration
   is self-consistent only for impact-to-settlement delays in `(0.40 s, 0.90 s)`, and that exceeding
   the upper bound produces baseline contamination and a characteristic false reject. *Evidence:
   analytical, derived from code constants; the actual delay distribution is* `[TO BE MEASURED]`.
7. **A reproducible evaluation protocol** with baselines, mechanism ablations, an adversarial and
   nuisance matrix, explicit metric denominators, and leakage controls across capture sessions and
   physical units (Section VII).

Contributions 2–5 are *design choices and hypotheses*. We have not established that any of them
improves a measurable outcome, and we do not assert that they are unprecedented in the whole
literature; Section II states precisely which elements have close prior art.

### E. Structure

Section II reviews cart systems, retail visual verification, multimodal retail sensing and the
systems background, and gives a comparison table. Section III formalises the task and derives
requirements. Section IV gives the architecture. Section V gives the algorithms, equations and the
timing analysis. Section VI documents the implementation. Section VII gives the evaluation protocol.
Section VIII reports the software checks that *were* run and discusses what they do and do not
establish. Section IX states limitations and threats to validity. Section X concludes.

---

## II. Related Work

### A. Identification-centric carts: RFID and barcode lineage

The dominant historical cart architecture reads an identifier and bills it. RFID carts with mobile
billing [15] and earlier RFID/ZigBee automatic-billing carts [16] establish that wireless cart
billing long predates camera-based verification. Two of the supplied comparators sit in this lineage.
A 2022 cart uses an EM-18 reader with a ZigBee/ESP uplink, an LCD running total and online/offline
modes [17]; its experimental discussion concerns reader behaviour versus distance and item removal,
not SKU-level visual identity. We note a specification conflict within that paper: its method text
names a 125 kHz EM-18 reader while its component table lists an 860–960 MHz RFID band. We therefore
cite it for its architecture and workflow only and rely on component datasheets for electrical
facts.

A second 2022 comparator combines YOLO-based image counting with an RFID *wallet* for payment and a
weight sensor that compares an aggregate basket total against an expected total [18]. Two
distinctions matter for this paper. First, an RFID payment card is not a per-product tag; conflating
the two overstates the identification coverage of such systems. Second, that paper's own conclusion
states that the implemented project classifies and prices items **without considering their brands**
— a material difference from verifying a specific branded SKU. Earlier Springer cart work in the same
lineage [19] and a secure-shopping architecture with an explicit communication protocol [20] round
out the identification-first family. None of these establishes that identifier reading alone resolves
product substitution: a correct identifier read is consistent with a different physical object being
placed in the basket.

### B. Weight-centric carts and reconciliation

Load-cell carts and racks [21], anti-theft carts combining RFID/ZigBee with weight [22] and
theft-control cart prototypes [23] form the weight-centric family. The most directly relevant recent
work is a 2026 load-cell-assisted weight-reconciliation algorithm for fraud detection [8]. It
addresses exactly the engineering problems this paper's mass gate faces: vibration noise on a moving
cart, the latency between scanning and weight settling, and drift. Its design uses an HX711 at
80 SPS with a 10-sample moving-average filter and a tolerance window with a constant drift offset;
it reports a weight-measurement error averaging 0.87 % over four grocery items at *n* = 30 trials
each, a fraud-detection confusion matrix over 100 simulated transaction cycles (46 TP, 4 FN, 2 FP,
48 TN), derived accuracy 94.0 %, precision 95.8 %, recall 92.0 %, an approximately 420 ms
scan-to-verification delay, and a false-positive rate below 4 % with filtering versus 28 % without.
Those are that paper's measurements under its conditions and are reproduced here only as attributed
prior art.

Three observations follow. First, the headline "96 % weight detection accuracy" in that paper's
abstract is not directly derivable from its Table I (whose average error of 0.87 % implies a much
higher figure) or from its Table III (94.0 % accuracy); readers comparing against it should quote the
table values. Second, several entries in its reference list could not be resolved to identifiable
venues (for example a "IEEE Transactions on Retail Automation" and a page range of 12345–12356 in
*IEEE Access*), so we cite it for its own described method and reported results and do not follow its
citation graph. Third, and most importantly for positioning: its future work proposes "adding
computer vision as a secondary verification method … to resolve ambiguities with items that have
identical weights". NXTCart implements that direction. That makes NXTCart a *complement* to [8],
not a claim of priority over it, and it means NXTCart's visual gate must be evaluated specifically on
the equal-mass cases where a weight gate is provably uninformative.

### C. Camera-plus-weight carts

A 2019 billing cart pairs a YOLO-style detector with an HX711 load cell for produce; it reports
3 classes (potato, tomato, carrot) and 70 % object-detection accuracy, with the load cell calibrated
to 5 kg [24]. A 2024 cart uses a Raspberry Pi 4, an Arduino Mega 2560, four 100 kg load cells via
HX711 and an Edge Impulse–trained model over 5 items; its reported evaluation is a 6-position weight
distribution test and a qualitative statement that performance was good for one beverage, acceptable
for a second, and problematic for a cucumber [25]. Notably, that system introduces an "Unknown item"
state when the camera fails to recognise an object but the scale detects an addition, and blocks
checkout until the item is removed — the same *function* as NXTCart's unreconciled-mass block, which
we therefore do not claim as new.

The supplied TAV-Cart paper [26] is the closest *design* comparator: barcode scanners plus a
strain-gauge load cell plus a camera-based scanner that is stated to "ensure the product being placed
in the cart is the right one, thus no item switching will occur", with cloud validation, an LED
status strip, a manual item-validation mode and UPI payment. It is explicitly presented as an initial
concept — "these computerized strategies and hardware devices are presented as an initial concept" —
and contains no quantitative evaluation. This is instructive: the asserted elimination of item
switching is exactly the kind of claim this paper refuses to make for NXTCart, because a single
camera cannot certify a fully occluded exchange (Section IX).

A 2026 multimodal cart [27] uses a Raspberry Pi 5, HX711 load cells, an Intel RealSense D435i
active-stereo depth camera, YOLOv11 trained on store products, A* in-store navigation and a Firestore
backend. Its anti-theft logic is a depth-intrusion detector that, on a mass anomaly without a
preceding barcode trigger, holds checkout and prompts a rescan. Its results section is an interface
walkthrough with qualitative statements ("through rigorous testing, it was verified that this model
could effectively detect and identify a number of physical objects"); no accuracy, latency or
detection-rate figures are reported. Cloud/edge cart baselines [28], [29] and an AI-driven cart with
tracking and inventory forecasting [30] complete the family; the latter is relevant to NXTCart only
as context for *proposed* extensions, since NXTCart implements no forecasting or navigation.

The supplied 2025 fusion cart [9] is the closest *method* comparator. It instruments a cart with an
RGB-D camera, a load cell and an RFID reader, triggers YOLOv8-s detection on a stabilised weight
change, models weight consistency as a Gaussian-like compatibility score and RFID as a binary
support score, and fuses the three into a weighted sum whose argmax is the predicted SKU, with a
low-confidence branch asking the shopper to confirm. It reports, on a self-collected set of 1000
products, approximately 75 000 labelled frames and 80 000 event instances: 98.7 % event-level top-1,
0.8 % misidentification and 0.3 s per item, against 93.5 % (vision-only) and 95.0 % (RFID-only)
baselines, with a V/V+W/V+R/V+W+R ablation.

Four differences define NXTCart against [9]. (i) **Objective:** [9] *recognises* which SKU an event
corresponds to; NXTCart *verifies* a scanned expectation and is permitted to refuse. (ii) **Fusion:**
[9] combines modalities into one score, so strong visual confidence can compensate for an
inconsistent mass; NXTCart keeps the gates independent and conjunctive precisely to forbid that
compensation. (iii) **Evidence extent:** [9] selects key frames around the event; NXTCart retains
every delivered frame in the window and refuses to decide when the window is sparse or gapped.
(iv) **Region content:** [9] embeds detector outputs; NXTCart embeds only pre-entry-baseline
differences, which is a stronger restriction but introduces its own failure modes (Section IX).

We also record, as the supplied-paper audit does, that [9] has internal citation inconsistencies: its
introduction attributes shelf monitoring to reference [6] while its list assigns [6] to a general
machine-learning paper, attributes a multimodal e-commerce dataset to [9] while its list assigns [9]
to yoghurt-cup recognition, prints two entries numbered [7], and cites a [15] that does not exist in
a list ending at [14]. Separately, a 70/10/20 split described as performed "at the SKU level to avoid
leakage" is difficult to reconcile with evaluating a fixed-class YOLOv8 classifier, whose output layer
cannot predict held-out classes. We treat these as reproducibility questions for the authors, not as
refutations of the method, and we do not copy that paper's citation mapping.

### D. Retail visual recognition and verification

Automatic-checkout research on conveyor video follows a detect-and-track-and-count paradigm; DeepACO
combines Scaled-YOLOv4 with SORT and reports an F1 of 0.4783 (second place) on the 2022 AI City
Challenge Track 4 test set A over 116 product identities, trained from 116 500 synthetic composites
[31]. That F1 is a useful calibration for expectations: fine-grained retail identification from video
is hard even for strong, purpose-built pipelines. Benchmarks such as RPC [32], densely packed shelf
detection [33], hierarchical grocery datasets [34] and digital-twin training data [35] define the
recognition task; multi-camera kiosk classification [36] and context-aware fine-grained retail
classification [37] address viewpoint and lookalike confusion. General-purpose representations such
as CLIP [38] and DINOv2 [39] and recent SKU-level retrieval studies with open vision-language models
[40] are plausible replacements for our frozen MobileNetV2 and are listed as future comparators, not
as implemented alternatives.

The most informative comparator for our decision rule is the few-shot pipeline of [10]: RT-DETR
localisation followed by metric-embedding similarity against a reference database, requiring no
retraining for new SKUs. It reports 79.67 % Precision@1 and 49.79 % mAP at 10 classes, degrading to
67.53 % Precision@1 and 38.07 % mAP at 40 classes, with hyperbolic embeddings outperforming Euclidean
at 24.65–81.09 ms per inference and a forgetting rate under 10 %, and it attributes the dominant
error source to classification among visually similar products rather than to localisation. Two
consequences for NXTCart are direct. First, since NXTCart uses the *same* family of mechanism
(crop → frozen embedding → nearest reference) with a weaker backbone, we must not expect better
open-set behaviour, which is itself the argument for verifying against a scanned expectation and
refusing when uncertain rather than identifying. Second, because visually similar products dominate
the error, the lookalike and equal-mass cases in Section VII are the decisive experiments, not the
easy ones.

It is therefore essential to separate three tasks that the literature often blurs:

* **Object-category recognition** — "this is a tomato" [24]. Category-level, small label set,
  insensitive to brand.
* **Fine-grained branded-SKU identification** — "this is brand *X* 100 g soap, not brand *Y*"
  [10], [31], [32], [37]. Open-set, large label set, dominated by lookalike confusion.
* **Verification against a scanned expectation** — "is this consistent with the SKU whose barcode was
  just read, and may I refuse to answer?" [3], [11]. Binary with abstention, conditioned on a
  declared identity.

NXTCart performs the third task and uses all-SKU scoring only as a *contrastive device* within it,
not as an identification claim.

### E. Multimodal retail sensing and fusion theory

Shelf-side systems combining vision, weight and location — FAIM [41] and AIM3S [42] — are the
strongest open prior art on how mass and image evidence interact in retail, including their failure
cases; their shelf setting differs from a cart in that shelf mass is partitioned per product
position, whereas a cart's single aggregate load cell cannot attribute simultaneous placements.
Classical [43] and modern [44] multisensor-fusion treatments frame evidence combination and
uncertainty, but general fusion theory does not establish that this cart's channels are independent:
the Pi's delta computation and the Arduino's comparison share one load cell, so their agreement is
*computational* redundancy, not sensor redundancy (Section IX). Finally, work on neural-network
calibration [45] and selective classification [14] underpins our refusal behaviour: a cosine
similarity is not a probability of correct verification, and a system that may abstain should be
characterised by risk against coverage rather than by accuracy alone.

### F. Systems and methods background

ROS 2 [13] supplies the distributed substrate, and its quality-of-service model [46] is what makes
frame loss an explicit, observable design parameter rather than a hidden failure. Detector [47] and
tracker [48], [49] foundations are cited because the cart literature is built on them and because
NXTCart's retired predecessor used tracking; the current runtime contains no detector and no tracker,
and we therefore do not report tracking metrics.

### G. Comparison table

TABLE I summarises the comparators on the dimensions that matter for this paper. "Not reported" means
the information is absent from the source we read, at the depth stated in the disposition supplement;
it is not an assertion that the system lacks the property.

**TABLE I. Comparison of cart and checkout systems on verification-relevant dimensions.**
("FT" = full text read; "MD" = metadata/abstract level only. Figures are each source's own, under its
own conditions, and are not comparable across rows.)

| Ref | Year | Read | Identification method | Role of vision | Role of weight | Temporal / event association | Computation location | Measured task and reported result | Stated limitations |
|---|---|---|---|---|---|---|---|---|---|
| [9] | 2025 | FT | RGB-D vision + load cell + RFID, decision-level fusion | Primary recogniser (YOLOv8-s), fused score | Gaussian-like compatibility score over catalogue nominal mass | Weight-change trigger; short frame window; IoU tracking inside window | Embedded SoC on cart, 8-bit quantised | Event-level top-1 over 1000 products, ~80 000 events: 98.7 % acc., 0.8 % misID, 0.3 s/item; V 93.5 %, V+W 96.1 %, V+R 97.3 % | Occlusion, tag conflict; internal citation inconsistencies; SKU-level split vs fixed-class head unresolved |
| [8] | 2026 | FT | Barcode + load cell only (no camera) | None | Primary: delta matching vs catalogue mass, tolerance window + drift offset | Scan event or weight-change event within a time window T; 10-sample moving average | ESP32 edge node + tablet app, cloud DB | Weight error 0.87 % avg (4 items, n=30 each); 100 simulated cycles: 94.0 % acc., 95.8 % prec., 92.0 % rec.; ~420 ms; FPR <4 % (vs 28 % unfiltered) | Items <20 g exempted; equal-weight items unresolved (vision proposed as future work); several unresolvable references |
| [26] | 2024 | FT | Barcode scanners (laser, optional camera-based) | Asserted anti-switching check; not evaluated | Continuous strain-gauge monitoring, cloud cross-check vs expected mass | Continuous monitoring; manual/auto "item validation mode" before billing | Cart CPU + cloud (DynamoDB/Firestore) | None — explicitly an initial concept | No evaluation; horizontal barcodes unscannable by laser pair |
| [27] | 2026 | FT | Barcode + load cell + active-stereo depth | Depth-intrusion detection; YOLOv11 content audit | Primary: mass vs barcode-declared mass | Depth intrusion *without* preceding barcode trigger → anomaly, checkout hold | Raspberry Pi 5 on cart + Firestore | Qualitative interface walkthrough; no accuracy, latency or detection rate reported | Future work is integration/optimisation; no quantitative validation |
| [10] | 2025 | FT | Vision only: RT-DETR v3 localisation + metric embeddings | Entire pipeline; nearest-reference classification, no retraining | None | None (single shelf images) | Workstation (not reported as embedded) | Shelf-Product dataset: 79.67 % P@1 / 49.79 % mAP at 10 classes; 67.53 % / 38.07 % at 40; 24.65–81.09 ms; forgetting <10 % | Errors dominated by visually similar products; IoU ≈0.68 localisation ceiling |
| [31] | 2022 | FT | Vision only: Scaled-YOLOv4 + SORT, detect-track-count | Entire pipeline | None | Track IDs; count when object fully inside ROI | Not reported as on-cart | AI City 2022 Track 4 test-set A: F1 = 0.4783 (2nd place), 116 IDs, 116 500 synthetic composites | Occlusion, motion blur, item similarity; synthetic-to-real gap |
| [17] | 2022 | FT | RFID (EM-18) | None | Display of product weight only | None | Arduino Nano + ESP8266 + ZigBee, cloud billing | Reader behaviour vs distance and item removal | No SKU-level identity verification; internal 125 kHz vs 860–960 MHz conflict |
| [18] | 2022 | FT | RFID tags on product *groups* + RFID wallet for payment | YOLOv3 item counting | Aggregate basket total vs expected total | None | On-cart compute + Wi-Fi | Example detections; counting described | Own conclusion: classifies and prices **without considering brands** |
| [24] | 2019 | FT | Vision only (produce), presented to camera | Category classifier | Per-item mass for variable-weight pricing | None | Arduino + host | 3 classes; 70 % detection accuracy; load cell to 5 kg | Category-level only; barcodes/RFID impractical on produce |
| [25] | 2024 | FT | Barcode + vision (Edge Impulse model) | Category recogniser; "Unknown item" state blocks checkout | 4× 100 kg load cells; unscanned-addition detection | None | Raspberry Pi 4 + Arduino Mega 2560 | 5 items; 6-position weight distribution test; qualitative per-item outcomes | Cucumber recognition problematic; no aggregate metrics |
| [41] | 2020 | MD | Shelf vision + weight + location fusion | One fused channel | One fused channel, partitioned per shelf position | Shelf-event based | Store infrastructure | Inventory-monitoring accuracy (abstract level) | Shelf setting; not a cart; full text pending |
| [42] | 2019 | MD | Multimodal shelf sensing, cashier-less store | One fused channel | One fused channel | Store-event based | Store infrastructure | Inventory monitoring (abstract level) | Shelf setting; full text pending |
| [3] | 2022 | MD | Declared product vs observed, OCR + classification | Verification with conformal abstention | None | Per-presentation | Not reported | Product verification with Mondrian conformal prediction (abstract level) | Full text pending; OCR-dependent |
| **NXTCart (this paper)** | 2026 | — | **Barcode/QR primary; vision verifies the scanned SKU; vision never identifies independently** | **Foreground-only ROIs vs all SKUs; abstains; vetoes on confident alternate** | **Independent conjunctive gate: Pi delta check + Arduino firmware check on the same cell** | **Retrospective burst from a 4 s / 120-frame ring around a settled-mass timestamp; density + gap admissibility; txn/attempt binding** | **Pi: sensors, catalogue, ledger, checkout. Arduino: acquisition + mass verdict. PC: segmentation + ONNX embeddings** | **Software checks only (Section VIII-A); recognition, latency and detection rates** `[TO BE MEASURED]` | **No proof against occluded substitution; single aggregate cell cannot attribute concurrent placements; UPI QR is a payment request, not settlement** |

---

## III. Problem Formulation and Design Requirements

### A. Entities

Let `K` be the set of registered SKUs. The catalogue maps a barcode to a record
`(barcode, name, sku, w_e, tol, price)` where `w_e > 0` is the **gross packaged** mass in grams,
`0 < tol < w_e`, and `price > 0`; these constraints are enforced at import and at every lookup
(Section VI-B). A **unit** is one physical instance of a SKU in one cart session, identified by a
transaction identifier `τ` and an **attempt** counter `a ∈ ℕ⁺`. The pair `(τ, a)` is the association
key for every piece of evidence.

### B. Events and evidence

A session produces a sequence of events. For the `(τ, a)` of interest:

* `t_scan` — a barcode/QR decode accepted by the scan gate.
* `t_settled` — the host-clock timestamp of the first *stable, calibrated* scale sample whose
  deviation from the current anchor exceeds the noise threshold, and which the ledger assigns to this
  unit. **This is a stable-sample timestamp, not a mechanical impact interrupt.**
* `F = {(u_i, s_i, I_i)}` — the frame ring on the PC, where `s_i` is the source (Pi-clock) timestamp
  applied immediately after camera read, `u_i` the PC's monotonic receive time, and `I_i` a BGR
  image.

### C. The verification task

Given `(τ, a)`, the scanned SKU `k* ∈ K`, the settled mass delta `Δ`, and `F`, produce

* a **mass verdict** `V_w ∈ {PASS, FAIL, PENDING, CHECKING}`, and
* an **image verdict** `V_c ∈ {MATCH, MISMATCH, RETRY, UNAVAILABLE}` with a reason code,

such that a unit becomes billable only if both gates reach `PASS` for the **current** attempt, and
such that a system that cannot obtain admissible evidence **abstains** (`RETRY`) rather than guessing
in either direction. This is a selective-classification formulation [14]: coverage is a free variable
and must be reported alongside error.

### D. Threat and nuisance model

We separate adversarial cases from honest nuisances, because they have opposite cost asymmetries.

**Adversarial (must not be accepted):**
A1 barcode switching — scan a cheap SKU, insert an expensive one of different mass;
A2 equal-mass substitution — scan SKU *X*, insert same-mass SKU *Y* (mass gate provably uninformative);
A3 lookalike substitution — same brand family, different variant/size;
A4 unscanned insertion — insert without scanning;
A5 duplicate-scan exploitation — one physical unit billed once but scanned twice, or vice versa;
A6 removal fraud — select an expensive row for removal, physically remove a cheap equal-mass item;
A7 occlusion attacks — hand or already-present merchandise hides the inserted object;
A8 timing attacks — insert during a camera outage, a settlement wait or a restart window.

**Honest nuisances (must not be falsely rejected, or must be recoverable):**
N1 hands in frame; N2 shadows and lighting change; N3 motion blur; N4 partial occlusion by existing
basket contents; N5 dropped camera frames; N6 variable impact-to-settlement delay; N7 scale drift;
N8 cart movement during placement; N9 cancelled or retried placements; N10 service restarts.

### E. Derived requirements

**TABLE II. Derived design requirements and their implementation status.**

| ID | Requirement | Rationale | Status in current code |
|---|---|---|---|
| R1 | Evidence must be associable to exactly one `(τ, a)`; a verdict for one attempt must never satisfy another | A5, A6, A8 | Implemented: `(txn_id, attempt)` keys on both hosts; completed-key cache; mismatched identity → `RETRY` |
| R2 | Mass and image decisions must not compensate for each other | A2, A3 | Implemented: conjunctive gates; a camera `MATCH` cannot clear a mass `FAIL` |
| R3 | The visual evidence window must be chosen *after* the physical event is observed | N6 | Implemented: retrospective extraction from a bounded ring |
| R4 | Incomplete visual evidence must abstain, not decide | N5, N6 | Implemented: `burst_min_frames`, `burst_max_gap`, missing-baseline → `RETRY` |
| R5 | Background pixels must not enter the recognition network | N2, N4 | Implemented: foreground-only ROIs; global change refused |
| R6 | An early correct view must not outvote a later substituted object | A2, A3, A7 | Implemented: all-SKU scoring and burst-level swap veto |
| R7 | Unexplained mass must block checkout and be clearable only by returning to accounted mass | A4 | Implemented: unassigned-weight issue latches the checkout reason |
| R8 | Loss of observation must invalidate trust rather than be silently tolerated | A8, N10 | Implemented: camera-generation change, PC heartbeat gap and scale restart force reconciliation |
| R9 | State must survive restart without resurrecting unfinished units as verified | A8, N10 | Implemented: SQLite WAL journal; non-`VERIFIED` units are failed on load |
| R10 | Concurrency limits must be physical, not cosmetic: one aggregate cell cannot attribute simultaneous placements | A5, N8 | Implemented: overlapping unsettled placements are flagged ambiguous, never guessed |
| R11 | Payment authorisation must be distinguished from a payment request | — | Partially: a revision-gated UPI deep-link QR is generated; **no provider confirmation exists** |
| R12 | Light curtains, multiple cells, IMU compensation, navigation, inventory forecasting | future scope | **Not implemented**; documented as planned design only |

---

## IV. System Architecture

### A. Host responsibilities

**Figure 1** (specification in the artifacts supplement) shows three hosts with a deliberately rigid
split, enforced mechanically by an import-boundary check in the test runner (Section VI-F).

* **Arduino + HX711 (firmware).** Calibrated acquisition at ~10 Hz, a six-sample stability test, and
  an *independent* transaction-specific expected-mass comparison. Calibration is persisted in EEPROM;
  the device never auto-tares at boot.
* **Raspberry Pi (authority).** Owns both USB cameras, barcode/QR decoding, the read-only catalogue,
  the serial bridge, the durable per-unit ledger, the touchscreen, and **checkout permission**. The Pi
  loads no model, no embedding database, no reference photographs and no API credentials.
* **PC (verification service).** Owns the frame ring, foreground segmentation, the MobileNetV2 ONNX
  embedding database, and the verdict publisher. It imports nothing from the Pi package, decides no
  prices, and holds no cart state.

**The PC is advisory. The Pi is authoritative.** This is the single most important architectural
property: a compromised, lagging or restarted verification service can withhold approval but cannot
grant it, cannot alter a bill and cannot authorise payment.

### B. Topic graph and message contract

**TABLE III. ROS 2 interface contract (message definitions are byte-identical in both workspaces and
checked by CI).**

| Topic | Type | Publisher → Subscriber | QoS | Role |
|---|---|---|---|---|
| `/cart/camera/frame` | `sensor_msgs/Image` (bgr8) | Pi camera → PC | Pub: sensor data (best effort); Sub: best effort, depth 30 | Source-stamped frames; `frame_id = verification_camera/<stream-uuid>` carries camera generation |
| `/cart/scanned_item` | `ScannedItem` | Pi scanner → Pi authority, PC | Reliable, depth 50 | Barcode + `scan_id`. **Logged by the PC; never starts inference** |
| `/cart/verification_request` | `VerificationRequest` | Pi authority → PC | Reliable, depth 50 | `action ∈ {add, remove, cancel}`; creates or cancels verification context |
| `/cart/placement_settled` | `VerificationRequest` | Pi authority → PC | Reliable, depth 50 | `started_at` = settled-sample stamp. **The only inference trigger** |
| `/cart/vision_event` | `VisionEvent` | PC → Pi authority | Reliable, depth 50 | Verdict + reason code + scores, bound to `(txn_id, attempt, action)` |
| `/cart/vision_health` | `std_msgs/String` (JSON) | PC → Pi authority | Reliable, depth 10 | 2 Hz heartbeat: `ready`, `generation`, `inflight`, `collecting`, `buffered_frames`, `camera_age_seconds` |
| `/cart/scene_anomaly` | `std_msgs/String` | PC → Pi authority | Reliable, depth 10 | Camera restart notice → forces reconciliation |
| `/cart/weight_sample` | `WeightSample` | Pi bridge → Pi authority | Reliable, depth 50 | `stream_id`, `seq`, `grams`, `stable`, `calibrated`, receive stamp |
| `/cart/weight_expectation` | `WeightExpectation` | Pi authority → Pi bridge → Arduino | Reliable, depth 50 | `E,txn,baseline_g,expected_g,tolerance_g` |
| `/cart/weight_verdict` | `WeightVerdict` | Pi bridge → Pi authority | Reliable, depth 50 | Arduino's independent `PASS`/`FAIL` with measured delta |
| `/cart/ui_display` | `CartState` | Pi authority → GUI | Reliable, transient-local, depth 1 | Per-unit statuses, totals, `revision`, `checkout_allowed`, `checkout_reason` |
| `/cart/remove_request`, `/cart/checkout_request`, `/cart/checkout_quote`, `/cart/alerts` | `std_msgs/String` | GUI ↔ Pi authority | Reliable, depth 10 | Selected removal; revision-gated checkout quote |

A deliberate asymmetry: image transport is **best-effort** on both ends, so frames may be lost by
design [46]. Rather than hiding that loss, the burst admissibility test (Section V-B) makes it an
explicit, reported outcome.

### C. Durable per-unit state

Each unit is a record `(τ, barcode, name, sku, w_e, price, tol, created, V_w, V_c, reason,
measured_g, action, a, V_ard, awaiting_weight, scan_id)` persisted to SQLite in WAL mode with
`synchronous=FULL`, alongside an append-only audit table and a monotonically increasing `revision`.
The derived display status is

```
status(u) = FLAGGED   if FAIL ∈ {V_w, V_c, V_ard}
          = VERIFIED  if V_w = V_c = PASS
          = VERIFYING  otherwise
```

with a separate `REMOVING` branch for in-progress removals. On process start, any unit that is not
`VERIFIED` is forced to `FAIL` with an "interrupted verification" reason — a restart can never
resurrect an unfinished unit as billable (R9).

### D. Checkout predicate

Checkout is allowed only when **all** of the following hold, evaluated in this order so the shopper
receives the most actionable reason:

```
1. the cart is non-empty;
2. the scale is in a ready, non-recovery state;
3. a fresh (< 2.5 s) stable calibrated sample exists;
4. the PC heartbeat is fresh (< 2.5 s);
5. no global issue is latched (e.g. unassigned mass, overlap, capacity);
6. every unit has status VERIFIED;
7. |g_latest − Σ_u measured_g(u)| ≤ 10 g   (global mass reconciliation);
8. a merchant UPI address is configured;
9. the quote's revision equals the ledger's current revision.
```

Condition 7 is a *second*, aggregate mass check layered on top of the per-unit checks: a basket can
contain only correctly verified units and still be refused if the total does not reconcile.
Conditions 8–9 and the GUI's own 1.5 s freshness and `request_id` checks mean a displayed quote
closes as soon as the cart changes.

### E. What the shopper experiences

Accepted scans appear in the bill immediately with per-unit Weight/Camera indicators; both gates run
in the background. A flagged unit does **not** lock the scanner — shopping continues, and every
flagged unit must be resolved through the selected-removal flow before payment. This separates two
properties that are often conflated: **GUI responsiveness** (scan rows appear at once, and are never
blocked by a pending or failed earlier unit) from **physical concurrency restrictions** (described
next), which are a hardware observability limit and are enforced regardless of interface latency.

### F. Physical concurrency restrictions

With one aggregate load cell the system cannot attribute mass to individual simultaneous placements.
The ledger therefore enforces, independently of UI state:

* more than one unit `awaiting_weight` → **all** pending units are flagged ambiguous and a global
  overlap issue is latched;
* a new scan while any removal is in progress → the new unit's mass gate fails immediately;
* a scan while the scale is not ready or not fresh → the mass gate fails immediately;
* a mass step that cannot be attributed to exactly one pending unit → an "unassigned weight" issue is
  latched and the anchor is advanced so the evidence cannot be reused by a later scan.

A second placement may legitimately begin as soon as the previous unit's mass has settled, even while
its image inference is still running; up to eight verifications may be in flight.

---

## V. Methodology and Algorithms

### A. Frame ingestion and the bounded ring

Each accepted frame is stored as `(u_i, s_i, I_i)` in a deque bounded to `N_buf = 120` entries and
pruned to `T_buf = 4.0 s` of receive time. A frame is rejected if its encoding, dtype or dimensions
are invalid, if its source-clock age `age = t_now − s_i` falls outside `[−0.5 s, 5.0 s]`, or if its
source stamp does not strictly exceed the previous stamp for the same camera generation (a replayed
physical frame must not supply a second sample). A change of `frame_id` is treated as a **camera
generation change**: the ring is cleared, all pending/collecting/running work returns `RETRY`, and a
scene-anomaly notice forces basket reconciliation on the Pi.

Memory and bandwidth follow directly from the configuration:

```
M_ring = N_buf · W · H · 3 = 120 · 640 · 480 · 3 B = 110.6 MB            (1)
B_net  = W · H · 3 · f     = 640 · 480 · 3 · 30 B/s = 27.6 MB/s ≈ 221 Mb/s  (2)
```

Both are **analytical** figures for raw BGR payload only; DDS, IP and framing overhead, worker
snapshots and ROS internal buffers add to both, and the achieved figures are
`[TO BE MEASURED: achieved publish rate, achieved receive rate, achieved wire bandwidth, PC RSS]`.

### B. Settlement-triggered burst assembly

On `/cart/placement_settled` with `(τ, a)`, the node validates that the settlement matches the
requested transaction (scan id, barcode, resolved SKU and action must all agree, else `RETRY`), that
the SKU resolves in the embedding database (else `UNAVAILABLE`), that the settlement stamp age lies in
`[−0.1 s, T_buf]` (else `RETRY`, flagging clock skew), and that the in-flight limit is not exceeded.
It then registers a **collection** rather than snapshotting immediately, because the post-event frames
have not necessarily arrived and the two topics may be reordered.

Let `t_s` be the settlement stamp in nanoseconds. Define

```
window  W(t_s) = [t_s − δ_pre, t_s + δ_post],   δ_pre = 0.40 s, δ_post = 0.15 s   (3)
baseline target b(t_s) = t_s − δ_base,          δ_base = 0.90 s                   (4)
baseline candidates B = { (u,s,I) ∈ F : b − δ_tol ≤ s ≤ b },  δ_tol = 0.15 s      (5)
```

Collection completes when the newest received source stamp passes `t_s + δ_post`, or when a transport
grace period of `T_grace = 0.75 s` after the nominal window end expires — whichever comes first. The
burst is then `S = { (u,s,I) ∈ F : t_s − δ_pre ≤ s ≤ t_s + δ_post }`, and it is **admissible** only if

```
B ≠ ∅                                                                             (6)
|S| ≥ n_min = 12                                                                  (7)
max gap over the padded stamp sequence ≤ g_max = 80 ms,
   where gaps are taken over [window_start, s_1, …, s_|S|, window_end]             (8)
```

Including both window edges in (8) is deliberate: a burst that is dense in the middle but missing its
first or last 100 ms would otherwise pass. At 30 FPS an admissible burst is normally 16–17 frames. If
(6) fails the verdict is `RETRY` ("pre-entry baseline unavailable"); if (7) or (8) fail the verdict is
`RETRY` ("incomplete placement burst"). The chosen baseline is `max(B)` by source stamp, i.e. the
newest frame at or before `b(t_s)`.

**Algorithm 1 — Settlement-triggered burst assembly (PC).**

```
Input: settlement message m with (τ, a, barcode, sku, action, t_s); frame ring F;
       parameters δ_pre, δ_post, δ_base, δ_tol, n_min, g_max, T_grace, T_buf
Output: (baseline, burst, metadata) or a RETRY/UNAVAILABLE verdict

 1 if (τ,a) already completed, running or collecting: return                 # idempotence
 2 c ← pending.pop((τ,a))  or  context_from(m)
 3 if identity(c) ≠ identity(m):          publish RETRY "settlement mismatch"; return
 4 if resolve(sku, barcode) = ⊥:          publish UNAVAILABLE "unknown SKU";   return
 5 age ← now_hostclock() − t_s
 6 if age ∉ [−0.1, T_buf]:                publish RETRY "stale settlement";    return
 7 if |collecting| + |running| ≥ 8:       publish RETRY "queue full";          return
 8 wait ← max(0, δ_post − age)
 9 collecting[(τ,a)] ← (c, t_s, ready_at = now+wait, deadline = now+wait+T_grace)
10
11 # later, on every 20 Hz tick:
12 for (τ,a) ∈ collecting:
13     covered ← newest_source_stamp ≥ t_s + δ_post
14     if now < ready_at or (¬covered and now < deadline): continue            # keep receiving
15     remove (τ,a) from collecting
16     B ← { f ∈ F : t_s − δ_base − δ_tol ≤ stamp(f) ≤ t_s − δ_base }
17     S ← { f ∈ F : t_s − δ_pre        ≤ stamp(f) ≤ t_s + δ_post }
18     if B = ∅:                          publish RETRY "no pre-entry baseline"; continue
19     gaps ← diffs([t_s−δ_pre] ++ stamps(S) ++ [t_s+δ_post])
20     if |S| < n_min or max(gaps) > g_max:
21                                        publish RETRY "incomplete burst";     continue
22     submit verify_burst(newest(B), S, c) to the single inference worker
```

### C. Foreground extraction

For a baseline `B` and a burst frame `I` of identical geometry, the mask is the thresholded
**per-channel maximum** absolute difference — chosen over a grayscale difference so that a change
between two similarly bright but differently coloured surfaces is preserved:

```
D(x)  = max_{c ∈ {B,G,R}} | B_c(x) − I_c(x) |                                     (9)
M(x)  = 1[ D(x) > τ_d ],  τ_d = 25                                               (10)
M'    = close_{5×5}( open_{3×3}( M ) )                                           (11)
```

using standard binary morphology [55]. Two refusals follow, both of which prevent background from
reaching the network:

```
if  Σ_x M'(x) > ρ · H · W,  ρ = 0.65   →  reject: "global scene change"          (12)
```

and, per connected component with bounding box `(x,y,w,h)`, padding `p = 0.12`:

```
x₀ = max(0, x − ⌈pw⌉),  y₀ = max(0, y − ⌈ph⌉)
x₁ = min(W, x + w + ⌈pw⌉),  y₁ = min(H, y + h + ⌈ph⌉)                            (13)
if (x₁−x₀)(y₁−y₀) > ρ · H · W          →  reject: "box covers too much of scene"  (14)
```

Components with contour area below `A_min = 800 px` are discarded as noise; if more than eight
components survive, the frame is refused as "too many changed regions" — many disjoint changes
indicate camera shake rather than one inserted product, and failing closed is preferred to silently
discarding a possibly substituted object. Crucially, components are **never merged**: a hand and a
product at opposite corners stay two tight crops rather than becoming one scene-sized rectangle.

For a **selected removal** the roles are inverted: the departing product is present in the baseline
and absent from the burst frames, so the difference is computed with the burst frame as reference and
the **crops are taken from the baseline image**. Cropping the now-empty basket would embed background
and reintroduce exactly the leakage this design removes.

**Algorithm 2 — Foreground ROI extraction.**

```
Input: baseline B, frame I, parameters τ_d, A_min, p, ρ; action ∈ {placed, removed}
Output: list of crops, list of boxes, or a rejection reason

 1 if action = removed: swap(B, I)        # crops are then taken from the baseline image
 2 if shape(B) ≠ shape(I): return reject "frame geometry changed"
 3 M ← 1[ max_channel |B − I| > τ_d ]
 4 M ← morph_close(morph_open(M, 3×3), 5×5)
 5 if nonzero(M) > ρ·H·W: return reject "global scene change"
 6 C ← external contours of M, sorted by area descending
 7 crops, boxes ← [], []
 8 for contour ∈ C:
 9     if area(contour) < A_min: continue
10     box ← pad(bounding_rect(contour), p) clipped to image
11     if area(box) > ρ·H·W: return reject "box covers too much of scene"
12     append box, crop(I, box)          # I is the baseline when action = removed
13 if |crops| > 8: return reject "too many changed regions"
14 return crops, boxes
```

### D. Embeddings and per-region scoring

Each crop is resized to 224 × 224, converted BGR → RGB, scaled to `[0,1]` and normalised with the
ImageNet statistics used by the torchvision ONNX export, then transposed to NCHW. The embedding is
the 1280-dimensional global-average-pooling output — the standard "strip the classification head"
construction — L2-normalised:

```
z = GAP( MobileNetV2_body( normalise(crop) ) ) ∈ ℝ^1280,   e = z / ‖z‖₂          (15)
```

The classifier logits are **not** the reference space, and the extractor resolves the pooling layer at
start-up by probing for a 1280-element output, failing startup if none exists. Reference vectors
`r_{k,j}` are built offline from product crops by the same preprocessing, so references and live crops
share one framing domain. Appearance similarity is the maximum cosine over that SKU's references:

```
s(k, e) = clip( max_j ⟨ r_{k,j}, e ⟩, −1, 1 )                                     (16)
```

Colour evidence, when present, is an 80-bin HSV fingerprint: an 18 × 4 hue × saturation histogram over
*chromatic* pixels (`S ≥ 90` and `V ≥ 60`) concatenated with an 8-bin brightness histogram over
*achromatic* pixels (`S < 90`, `V ≥ 40`), so that white, grey and dark packaging are distinguishable.
With `h(·)` the L2-normalised fingerprint,

```
c(k, crop) = clip( max_j ⟨ h_{k,j}, h(crop) ⟩, 0, 1 ) ,     colour_ok ⇔ c ≥ 0.30  (17)
```

and, if a SKU additionally declares an expected mean BGR colour `μ_k`,

```
c_bgr = 1 − ‖ mean(crop) − μ_k ‖₂ / (255·√3) ,              colour_ok ⇔ c_bgr ≥ 0.30 (18)
```

with the reported colour score taken as the minimum of the two channels when both exist. Apparent
shape evidence uses only the crop's aspect ratio against reference aspect ratios `ρ_j`:

```
α = max(h,w)/min(h,w) ,   size_ok ⇔ ∃j : max( α/ρ_j , ρ_j/α ) ≤ 3.0               (19)
```

**Equation (19) is explicitly not a physical size measurement.** The camera is uncalibrated, there is
no depth channel and no known scale, so `α` is an image-plane ratio that varies with distance, pose
and crop tightness. It is a weak consistency filter and is treated as such; the tolerance of 3.0 is
correspondingly loose.

### E. All-SKU competition and the burst-level veto

For each region, all `|K|` SKUs are ranked by `s(k,e)` with a deterministic tie-break on the SKU key.
With `k₁` the top-1 SKU, `s₁` its score, `s₂` the runner-up score, `m = s₁ − s₂`, and `k*` the scanned
SKU, the per-region outcome is

```
if  k₁ ≠ k*  and  s₁ ≥ θ_swap = 0.70:
        MISMATCH / SWAP_DETECTED,  observed SKU = k₁                              (20)
elif k₁ = k*  and  s₁ ≥ θ = 0.72  and  m ≥ μ = 0.04  and  colour_ok ∧ size_ok:
        MATCH                                                                     (21)
else:   MISMATCH / LOW_CONFIDENCE                                                 (22)
```

For a removal with no expected SKU, the same rule applies with `k* = ⊥` and the margin requirement
`μ_rm = 0.04`. Aggregation over the whole burst is a **lexicographic precedence**, not a vote:

```
pool = swaps  if swaps ≠ ∅
     = matches  if swaps = ∅ and matches ≠ ∅
     = failures otherwise
verdict = argmax_{r ∈ pool} score(r)                                              (23)
```

Hence a single sufficiently confident alternate SKU anywhere in the burst overrides every matching
region — an early, correct, hand-held view of the scanned product cannot certify a different object
that was actually released. If no region produced a valid embedding at all, the outcome is
`UNAVAILABLE`/`NO_EMBEDDING`; if no region existed, the outcome is `MISMATCH`/`NO_ITEM_SEEN`.

Note the asymmetry between `θ_swap = 0.70` and `θ = 0.72`: accusation is marginally *easier* than
approval. That is intentional in a fail-closed design, but it also means a near-threshold lookalike
can produce a `SWAP_DETECTED` against an honest shopper. The honest-shopper cost of this asymmetry is
`[TO BE MEASURED: false SWAP_DETECTED rate on genuine placements]`.

**Algorithm 3 — Burst verification with all-SKU competition and veto.**

```
Input: expected SKU k*, region lists per burst frame, reference DB over K
Output: Result(verdict, sku, score, colour, reason, code, evaluations)

 1 if k* ∉ K: return UNAVAILABLE "no reference embeddings for scanned SKU"
 2 evaluations, swaps, matches, failures ← [], [], [], []
 3 for i, frame_regions ∈ enumerate(regions):
 4   for j, crop ∈ enumerate(frame_regions):
 5     if crop invalid or min(h,w) < 8: record UNAVAILABLE for (i,j); continue
 6     e ← normalise(embed(crop))
 7     ranked ← sort_desc_by_score([ (score(k, crop, e), k) for k ∈ K ])
 8     (s₁, c₁, ok₁), k₁ ← ranked[0];  s₂ ← ranked[1].score;  m ← s₁ − s₂
 9     if k₁ ≠ k* and s₁ ≥ θ_swap: append SWAP_DETECTED(k₁, s₁) to swaps
10     elif k₁ = k* and s₁ ≥ θ and m ≥ μ and ok₁: append MATCH(k*, s₁) to matches
11     else: append LOW_CONFIDENCE(k*, s₁) to failures
12     record (i, j, k₁, s₁, s(k*), k₂, s₂, m, c₁, ok₁, verdict, code)
13 pool ← swaps or matches or failures            # lexicographic precedence
14 return argmax_score(pool) with all evaluations attached, else UNAVAILABLE/NO_EMBEDDING
```

### F. Independent mass verification

Two comparisons are made over the same physical signal. The firmware maintains a six-sample ring at
~10 Hz and declares

```
stable  ⇔  calibrated  ∧  |ring| = 6  ∧  (max ring − min ring) ≤ σ = 4.0 g        (24)
```

publishing the window mean when stable and the instantaneous reading otherwise. On a Pi-supplied
expectation `(τ, baseline_g, w_e, tol)` it emits, once a stable reading deviates from `baseline_g` by
more than 5 g,

```
Δ_ard = reading − baseline_g ,      PASS ⇔ | Δ_ard − w_e | ≤ tol                  (25)
```

Independently, the Pi's ledger computes its own delta against its own anchor and requires

```
Δ_pi = g − anchor ,                 PASS ⇔ | Δ_pi − w_e | ≤ tol                   (26)
```

A unit's mass gate becomes `PASS` only when (26) holds **and** the firmware verdict (25) has also
passed; while the firmware verdict is outstanding the gate sits in `CHECKING`, and a firmware `FAIL`
is terminal and cannot be overwritten by a later pass. A missing verdict times out to `FAIL` after
the 20 s ledger deadline and the firmware's own 20 s expectation timeout. This is redundancy of
*computation and of expectation plumbing*, not of sensing — see Section IX-C.

### G. Does the configured window capture the physical insertion?

This is the question the configuration most depends on, and it can be answered analytically from the
shipped constants without any hardware.

Let `t_0` be mechanical impact and `t_q ≥ t_0` the moment the reading first enters a band of width
≤ σ = 4 g and stays there. Because stability requires six consecutive 100 ms samples inside the band,
the first sample that can be marked stable is the sixth, i.e. no earlier than `t_q + 0.5 s`, and in
practice `t_q + 0.5…0.6 s` depending on sample phase. The Pi stamps the sample on serial receipt,
adding transmission and USB-CDC latency on the order of milliseconds. Writing
`Δ_s = t_settled − t_0 = (t_q − t_0) + Δ_stab + Δ_serial` with `Δ_stab ∈ [0.5, 0.6] s`:

```
descent inside the window  ⇔  Δ_s ≤ δ_pre = 0.40 s                                (27)
baseline strictly pre-entry ⇔  Δ_s < δ_base = 0.90 s                              (28)
```

**Condition (27) is unsatisfiable with the shipped firmware,** because `Δ_stab` alone exceeds
`δ_pre`. The configured burst therefore does **not** observe the product in flight; it observes the
product *at rest* in the basket, and possibly the hand withdrawing. This is not necessarily a defect —
a settled product is still foreground with respect to a pre-entry baseline, and the absence of the
hand reduces occlusion — but it has three consequences that must be stated rather than assumed away:

1. The 16–17 frames of an admissible burst are **near-duplicates** of one static scene. Density buys
   robustness against packet loss and shutter noise, not viewpoint diversity. Claims that depend on
   temporal diversity (for example, that a burst sees multiple faces of a package) are unsupported.
2. The margin before baseline contamination is thin. Combining (28) with
   `Δ_s ≥ Δ_stab ≈ 0.5…0.6 s` leaves roughly **0.30–0.40 s of mechanical decay budget**. Because the
   selected baseline is the newest frame at `t_settled − 0.90 s`, once `Δ_s > 0.90 s` the baseline
   itself already contains the product at rest; the difference mask then collapses and the system
   emits `MISMATCH`/`NO_ITEM_SEEN` — a **false reject with a misleading reason code**, not a timeout.
3. The self-consistent operating band for the current configuration is therefore

```
0.40 s  <  Δ_s  <  0.90 s                                                         (29)
```

which must be verified empirically for the actual mechanism, product mass range and mounting
stiffness: `[TO BE MEASURED: distribution of Δ_s = t_settled − t_impact over ≥ 200 drops, per mass
decile, on the mounted cart]`. If the distribution's upper tail crosses 0.90 s, the correct responses
are to widen `δ_base` (and `T_buf` accordingly), to reduce `Δ_stab` by raising the HX711 sample rate
or shortening the stability window at the cost of noise immunity, or to add a **separately defined
impact timestamp** — for example a first-derivative threshold crossing published alongside the
settled sample. Lowering the confidence thresholds to compensate for missing evidence is explicitly
not an acceptable response, because it trades a false reject for a false accept.

**Figure 6** (artifacts supplement) plots `Δ_s` against the three regimes: descent captured
(`Δ_s ≤ 0.40`, unreachable), valid at-rest observation (`0.40 < Δ_s < 0.90`), and baseline
contamination (`Δ_s ≥ 0.90`).

### H. Outcome codes and their consequences

**TABLE IV. Verdict and reason codes, as implemented, with their effect on the Pi.**

| Code | Verdict | Produced when | Effect on the unit | Effect on checkout |
|---|---|---|---|---|
| `MATCH` | `MATCH` | (21) holds for some region and no swap anywhere in the burst | `V_c ← PASS` | Permitted if mass gate also passed and global conditions hold |
| `SWAP_DETECTED` | `MISMATCH` | (20) holds for any region; takes precedence over all matches | `V_c ← FAIL`, reason carries the observed SKU | Blocked until the unit is resolved by selected removal |
| `LOW_CONFIDENCE` | `MISMATCH` | Regions exist but none satisfies (20) or (21) | `V_c ← FAIL` | Blocked |
| `NO_ITEM_SEEN` | `MISMATCH` | **No** foreground region in any burst frame | `V_c ← FAIL` | Blocked |
| `SCENE_CHANGED` | `RETRY` | At least one frame yielded regions **and** at least one frame was refused by (12)/(14) | `V_c ← FAIL` (the Pi treats a non-`MATCH` as a failed camera gate) | Blocked |
| `INFERENCE_ERROR` | `UNAVAILABLE` | The matcher raised inside the worker | `V_c ← FAIL` | Blocked |
| `NO_EMBEDDING` | `UNAVAILABLE` | Regions existed but none produced a valid embedding | `V_c ← FAIL` | Blocked |
| — (text reason) | `RETRY` | Missing baseline; sparse or gapped burst; stale settlement stamp; identity mismatch; queue full; camera restart; inference deadline exceeded; settlement never arrived | `V_c ← FAIL` | Blocked |
| — (text reason) | `UNAVAILABLE` | Scanned barcode/SKU not in the embedding database | `V_c ← FAIL` | Blocked |

Two implementation details deserve explicit statement because they are not obvious from the
documentation. First, `NO_ITEM_SEEN` is tested **before** `SCENE_CHANGED`: if *every* frame in a burst
is refused as a global scene change, the region count is zero and the result is
`MISMATCH`/`NO_ITEM_SEEN`, not `RETRY`/`SCENE_CHANGED`. Anyone interpreting the diagnostic manifests
should therefore read `NO_ITEM_SEEN` as "no usable foreground region was isolated anywhere in the
burst", a class that includes the total-illumination-change case; the per-frame `rejected` field in
the manifest distinguishes the two causes. The safety direction is identical either way — both paths
refuse. Second, the Pi collapses the four-valued image verdict to a binary gate — `PASS` only for
`MATCH` with `approved = true`, `FAIL` otherwise — so `RETRY` and `UNAVAILABLE` are *not* retried
automatically; the shopper's recovery path is selected removal and re-scan, which creates a fresh
transaction with an incremented attempt. Both behaviours are recorded here as observed properties of
the evaluated revision. No change to either is proposed in this paper.

### I. Concurrency, cancellation and liveness

All ROS callbacks run in the default mutually-exclusive callback group; all segmentation, inference
and diagnostic disk writes run on a **single** worker thread, so `cv2.dnn` is never entered
concurrently and camera/heartbeat callbacks never block behind inference. No worker publishes or
mutates node state: results are collected on the 20 Hz timer. The frame ring, the in-flight map
(≤ 8) and the completed-key cache (≤ 4096, FIFO-evicted) are all bounded.

Cancellation is handled at three points, each covered by a regression test: a `cancel` action removes
pending and collecting entries and marks a running future expired; an expired future's result is
discarded when it completes; and a verdict for an already-completed key is suppressed. A camera
generation change invalidates everything in flight. Heartbeats continue during inference and tolerate
a camera age up to 5.0 s even after old frames have been pruned, so a brief delivery stall does not
invalidate already-verified units — but a genuine camera restart does, via `/cart/scene_anomaly`.

---

## VI. Implementation

The system was inspected and tested at repository revision
`28aa58d3ceff6a7d03a2d208d9d4065606af85f8` (11 October 2026). All statements in this section are
derived from the launched source and configuration at that revision.

### A. Hardware and software inventory

**TABLE V. Inventory. Entries marked "requested" are driver requests, not measured achieved values.**

| Element | As specified in source / documentation | Note |
|---|---|---|
| Load-cell ADC | HX711, DT → Arduino pin 3, SCK → pin 2, 115200 baud serial [50] | Load-cell capacity, class and excitation are deployment choices, not fixed by the code |
| Scale library | `bogde/HX711` Arduino library [51] | Version/commit to be pinned for experiments |
| Calibration persistence | EEPROM record `{magic 0x4E585432, offset, factor}` [52]; `ZERO` then `CAL,<grams>`, each averaging 10 raw reads | Never auto-tares at boot; an uncalibrated device cannot verify |
| Stability window | `WINDOW = 6` samples, `STABLE_SPAN_G = 4.0 g`, ~100 ms sample gating | Documented as adding ≈0.6 s at 10 readings/s; both constants are tuning targets |
| Mass-change trigger | `CHANGE_G = 5.0 g` against the Pi-supplied baseline | Firmware-side independent check |
| Cart computer | Raspberry Pi, Ubuntu 24.04 + ROS 2 Jazzy; light desktop session for the Tk GUI | Exact model and RAM `[TO BE RECORDED]` |
| Scanner camera | USB webcam, 640 × 480 requested, `BUFFERSIZE = 1`, V4L2; pyzbar/ZBar decoding [53] | Decode rate and read range `[TO BE MEASURED]` |
| Verification camera | USB webcam, 640 × 480 at 30 FPS **requested**, `BUFFERSIZE = 1`, V4L2, `bgr8` | Driver-reported FPS is logged at open; achieved rate `[TO BE MEASURED]`. No MJPG FourCC is requested, so raw-format USB bandwidth may limit the achieved rate |
| Verification host | PC, Ubuntu 24.04 + ROS 2 Jazzy, OpenCV DNN CPU backend [54] | CPU model, core count and RAM `[TO BE RECORDED]` |
| Network / middleware | ROS 2 Jazzy, `ROS_DOMAIN_ID = 42`, `RMW_IMPLEMENTATION = rmw_cyclonedds_cpp`, shared trusted LAN with DDS UDP/multicast permitted | DDS security is not enabled; see Section IX-F |
| Model | MobileNetV2 [12], `mobilenetv2-7.onnx` (ONNX model zoo torchvision export, opset 7, ≈13.9 MB), 1280-D GAP output | Resolved at start-up by probing for a 1280-element output; start-up fails if absent |
| Preprocessing | 224 × 224, BGR→RGB, `/255`, mean `(0.485, 0.456, 0.406)`, std `(0.229, 0.224, 0.225)`, NCHW | Identical in the offline database builder and the live matcher |
| Inference engine | `cv2.dnn.readNetFromONNX` with `ENGINE_CLASSIC` where available, `DNN_BACKEND_OPENCV`, `DNN_TARGET_CPU` | No GPU, no ONNX Runtime, no remote API in the live path |
| Colour fingerprint | 18 H × 4 S chromatic bins + 8 achromatic V bins = 80; `S ≥ 90 ∧ V ≥ 60` chromatic, `S < 90 ∧ V ≥ 40` achromatic; format version 2 | A stale colour format disables colour, which makes the verifier stricter, never laxer |
| Catalogue | SQLite, read-only at runtime, validated on every lookup: non-empty barcode/name/SKU, finite values, `w_e > 0`, `price > 0`, `0 < tol < w_e`, SKU usable as a folder name | Scanner-supplied price/name fields are **not** trusted |
| Durable state | SQLite WAL, `synchronous = FULL`, state row + append-only audit table, monotonic `revision` | Default `~/nxtcart/cart_state.db` |
| Payment | Locally generated `upi://pay?pa&pn&am&cu=INR` QR, revision-gated [56] | **A payment request, not a provider-confirmed settlement** |

### B. Configured parameters

**TABLE VI. Configured defaults. These require empirical validation; none is an optimised or
experimentally justified value.**

| Group | Parameter | Value | Where | What it controls |
|---|---|---|---|---|
| Thresholds | `similarity_threshold` θ | 0.72 | `verification.yaml` | Minimum top-1 cosine for `MATCH` |
| | `competitive_margin` μ | 0.04 | " | Minimum top-1 minus runner-up |
| | `swap_threshold` θ_swap | 0.70 | " | Alternate-SKU score producing `SWAP_DETECTED` |
| | `colour_threshold` | 0.30 | " | Minimum colour-channel score |
| | `size_ratio_tolerance` | 3.0 | " | Apparent aspect-ratio tolerance (not physical size) |
| | `removal_margin` | 0.04 | " | Margin for open-SKU removal classification |
| Buffer | `buffer_seconds` | 4.0 s | " | Ring retention by receive time |
| | `buffer_max_frames` | 120 | " | Ring capacity (= 4 s at 30 FPS) |
| Burst | `burst_before` δ_pre | 0.40 s | " | Window start before settlement |
| | `burst_after` δ_post | 0.15 s | " | Window end after settlement |
| | `baseline_before` δ_base | 0.90 s | " | Baseline target before settlement |
| | `baseline_tolerance` δ_tol | 0.15 s | " | Baseline search window |
| | `burst_min_frames` n_min | 12 | " | Density admissibility |
| | `burst_max_gap` g_max | 0.08 s | " | Gap admissibility, edges included |
| | `transport_grace` T_grace | 0.75 s | " | Extra wait for late delivery |
| Health | `camera_loss_timeout` | 5.0 s | " | Frame-age tolerance in the heartbeat |
| Foreground | `difference_threshold` τ_d | 25 | " | Per-channel difference threshold |
| | `foreground_min_area` A_min | 800 px | " | Minimum contour area |
| | `roi_padding` p | 0.12 | " | ROI padding fraction |
| | `max_roi_fraction` ρ | 0.65 | " | Global-change and box-size refusal |
| Scheduling | `settlement_timeout` | 18.0 s | " | How long a pending context waits |
| | `result_timeout` | 6.0 s | " | Inference deadline |
| | `max_inflight` | 8 | " | Concurrent verification limit |
| | `debug_keep` | 100 | " | Retained diagnostic transactions |
| Pi ledger | `verification_timeout` | 20.0 s | `pi_sensors.launch.py` defaults | Per-unit overall deadline |
| | `sensor_timeout` | 2.5 s | " | Scale and PC-heartbeat freshness |
| | `noise_g` | 5.0 g | " | Mass-step noise gate |
| | `empty_tolerance_g` | 10.0 g | " | Empty-cart and reconciliation tolerance |
| | `max_units` | 200 | `verification.py` | Cart capacity |
| Scanner | `rearm_seconds` | 0.8 s | " | Observed absence before a code re-arms |
| Firmware | `WINDOW` | 6 | `cart_scale.ino` | Stability ring length |
| | `STABLE_SPAN_G` σ | 4.0 g | " | Stability span |
| | `CHANGE_G` | 5.0 g | " | Firmware trigger threshold |

Internal consistency is enforced at start-up rather than trusted: the node refuses to launch unless
all durations are finite and positive, all counts are positive integers,
`δ_base > δ_pre`, `T_buf > δ_base + δ_post + T_grace`, `n_min ≥ 2`, `N_buf ≥ n_min`,
`0 ≤ p ≤ 0.5`, `0 < ρ < 1` and `τ_d ≤ 255`. With the shipped values,
`T_buf = 4.0 > 0.90 + 0.15 + 0.75 = 1.80` and `N_buf = 120 = 4.0 s × 30 FPS`, so the ring is exactly
sized for the configured window at the requested frame rate — a 15 FPS camera would halve the ring
occupancy and fail the density test (7) rather than silently degrade.

### C. Scan admission

Repeated scans of the same code are gated by **observed absence**, not by a timer: a code re-arms
only after it has been continuously absent from the decoder output for 0.8 s. A camera outage calls an
explicit gap handler that resets absence timers, so an outage can never be mistaken for the code
leaving view — otherwise unplugging the scanner camera while holding a code would re-arm it. If more
than one code is visible simultaneously, no scan is emitted and the shopper is asked to present one
code at a time.

### D. Diagnostic artifacts

Each worker evaluation writes, to a UUID-named directory under `debug_frames/`, the baseline image,
every evaluated full frame, every ROI, and a `manifest.json` containing source timestamps, window
bounds, bounding boxes, per-region target/top-1/runner-up scores, margins, colour scores,
evidence flags, verdicts and reason codes. Filenames embed target SKU, predicted SKU, score and
verdict. Retention is bounded to the last 100 transactions, and **only** directories matching the
writer's own `nxtcart_<UTC>_<32-hex>` pattern are eligible for deletion; symlinked directories are
never followed and the parent is re-resolved immediately before recursive removal. A full or
unwritable disk is reported as an explicit error on the verdict and logged, and **cannot** change the
decision — a regression test asserts that a `MISMATCH` cannot become a `MATCH` because diagnostics
failed.

These artifacts are the intended instrument for the measurement campaign in Section VII, and they are
why the timing analysis of Section V-G is empirically checkable: the manifest records `settled_ns`,
`window_start_ns`, `window_end_ns`, `baseline_ns`, the realised frame count and the realised maximum
gap for every transaction. They are **diagnostic model outputs, not labelled ground truth**, and a
later cancellation or timeout can suppress publication of a verdict whose artifacts were already
written.

### E. Clock synchronisation assumptions

Both the camera stamps and the settlement stamps originate on the **Pi** clock; the PC compares them
against its **own** ROS clock to compute ages, and uses its monotonic clock only for scheduling and
retention. The deployment therefore requires NTP/chrony synchronisation between hosts, and simulated
time must never be mixed with wall-clock sensor stamps. Skew is not silently absorbed: a settlement
stamp outside `[−0.1 s, 4.0 s]` of the PC's clock returns `RETRY` naming clock synchronisation, and a
frame outside `[−0.5 s, 5.0 s]` is dropped. The residual exposure is a *slowly* accumulating skew
smaller than those windows, which would bias baseline and burst selection without triggering any
guard: `[TO BE MEASURED: Pi↔PC offset and drift over a shopping session]`.

### F. Deployment-boundary enforcement

The test runner parses every Python source on both hosts and fails the build if the Pi package imports
`ml`, `torch`, `tensorflow`, `onnxruntime` or `nxtcart_vision`, or if the PC package imports
`smart_cart`. It also asserts that the two copies of `smart_cart_interfaces` are byte-identical. The
architectural split of Section IV-A is thus a checked invariant rather than a convention.

### G. Retained but unlaunched code

The repository deliberately retains historical material that the integrated runtime does **not**
launch, and this must be stated to avoid architectural confusion. The PC package's console entry
points are exactly `vision_verify_node` and `capture_references`; `vision_verify_node` imports only
`local_matcher` and `burst`. Consequently the MOG2 motion detector, the three-window "journey"
verifier, the geometric tracking pipeline, the zone/custody/identity trackers under `pc/ml/`, the
`pc/legacy/` suites, the vision-API backend utilities, and the JPEG-carrying `CameraFrame` message are
**not part of the live path**. Three Pi modules (`esp32_vision_node`, `vision_verify_node`,
`simulate_shopping`) are retired stubs that raise on invocation, and the Pi's `pc_processing.launch.py`
raises a redirection error.

Two documentation artifacts remain stale at this revision and are superseded by the current vision
guide: the top-level README's description of "3–5 full-frame motion views", and the setup guide's
JPEG transport, `scanner_region`/`cart_region` parameters, nine-frame scan-to-rest journey and
vision-API backend. The setup guide's hardware mounting, HX711 calibration, catalogue import and
checkout principles remain applicable. Readers reproducing this work should resolve any architectural
question from `pc/config/verification.yaml`, the two launch files, and
`vision_verify_node.py` / `burst.py` / `local_matcher.py`.

---

## VII. Experimental Design and Evaluation Protocol

No part of this protocol has been executed. It is specified at a level intended to be directly
runnable, and every table it produces is left with explicit placeholders.

### A. Ground-truth units and denominators

Three nested units of analysis, each with its own denominator, must be reported separately; reporting
only the first is the most common error in this literature:

1. **Region/frame level** — one evaluated ROI. Denominator: ROIs reaching the matcher. Useful only for
   diagnosing the visual channel; it is *not* the system's output.
2. **Transaction level** — one `(τ, a)` attempt. Denominator: attempts of the relevant class. This is
   the natural unit for false accept/reject.
3. **Session level** — one complete shopping trip ending in a checkout decision. Denominator: sessions.
   This is the unit that matters commercially, because the system's output is a bill.

Ground truth is recorded by a human operator independently of the system: for each placement, the
true SKU, the true physical action (add/remove/none), the true mass measured on a reference scale, the
intended scenario class, and the wall-clock time. System logs are joined to ground truth by
`(τ, a)` **after** the session, never by trusting the system's own identification.

### B. Baselines

All baselines run on the same physical placements and the same recorded evidence, so differences
reflect the decision rule rather than the trial set.

**TABLE VII. Baselines.**

| ID | Baseline | Construction |
|---|---|---|
| B0 | **Barcode only** | Bill every accepted scan; no gate. Lower bound on error, upper bound on convenience |
| B1 | **Barcode + weight** | Require (25) ∧ (26); ignore all image evidence. Reproduces the family of [8] |
| B2 | **Barcode + vision** | Require the image gate; accept any mass. Isolates the visual channel |
| B3 | **Full system** | Conjunctive gates plus global reconciliation and checkout predicate |
| B4 | **Fused score (contrast)** | Replace the conjunction with a weighted sum of a mass-consistency score and the visual score, argmax above a threshold, in the style of [9]. Tests whether independence actually buys anything, or only costs coverage |

B4 is important for honesty: the conjunctive design is a *hypothesis*, and the experiment must be able
to show that fusion would have been better.

### C. Ablations of the claimed mechanisms

Each ablation removes exactly one mechanism from B3, replaying the **same** recorded bursts offline so
that only the decision changes.

**TABLE VIII. Mechanism ablations, each replayed offline on the same recorded bursts.**

| ID | Ablation | Replaces | Tests contribution |
|---|---|---|---|
| A-FG | Embed the full frame instead of foreground ROIs | Algorithm 2 | #3 (foreground-only inference) |
| A-ALL | Score only the scanned SKU; threshold absolutely | Equations (20)–(22) | #4 (all-SKU competition) |
| A-VETO | Keep all-SKU scoring but let any `MATCH` win | Equation (23) | #4 (burst-level veto) |
| A-MARGIN | Set μ = 0 | Equation (21) | Competitor-margin requirement |
| A-COLOUR | Disable the colour and aspect channels | (17)–(19) | Auxiliary evidence |
| A-DENSITY | Accept any burst with ≥ 1 frame; no gap test | (7)–(8) | #2 (density admissibility) |
| A-BASE | Use the frame immediately before settlement as baseline | (4)–(5) | Pre-entry baseline choice |
| A-SAMPLE | Decimate the burst to 5 evenly spaced frames | §V-B | Whether density matters at all |
| A-TRIG | Trigger on the scan instead of on settlement, with a fixed forward window | Algorithm 1 | #2 (retrospective selection) |

The retired full-frame and journey-based pipelines may be evaluated **only** as separately identified
experiments, re-run under the same conditions on the same recorded data; their historical development
numbers are not comparable and are not reported as results.

### D. Scenario matrix

**TABLE IX. Scenario matrix. "In scope" means the current code has an implemented, unit-tested
handling path; it does **not** mean the handling has been validated on hardware.**

| # | Scenario | Class | Expected system behaviour | In scope |
|---|---|---|---|---|
| S1 | Correct product, correct mass, clear view | honest | `MATCH` + mass `PASS`; `VERIFIED` | Yes |
| S2 | Correct product, wrong mass | honest error / A1 | Mass `FAIL`; image `MATCH` cannot clear it | Yes |
| S3 | Equal-mass different SKU | A2 | Mass may pass; `SWAP_DETECTED` expected | Yes |
| S4 | Lookalike variant, same brand family | A3 | `SWAP_DETECTED` or `LOW_CONFIDENCE`; never `MATCH` | Yes |
| S5 | Unscanned insertion | A4 | Unassigned-mass issue latches; checkout blocked | Yes |
| S6 | Duplicate scan of one physical unit | A5 | Second unit has no mass step → ambiguous/flagged | Yes |
| S7 | Two scans before either mass settles | A5 / N8 | Both flagged ambiguous; neither borrows evidence | Yes |
| S8 | Two objects inserted together | A5 | Ambiguous; no attribution attempted | Yes |
| S9 | Selected removal of the correct unit | honest | Removed only after mass **and** removal-identity pass | Yes |
| S10 | Select expensive row, remove cheap equal-mass item | A6 | Removal identity mismatch; no discount; reconcile | Yes |
| S11 | Hand prominently in frame at settlement | N1 | Separate ROIs, no merge; `MATCH` on the product ROI | Yes |
| S12 | Strong shadow cast across the basket | N2 | Either a rejected region or a refusal; never a false `MATCH` | Yes |
| S13 | Global lighting change during the burst | N2 | Refusal; surfaces as `NO_ITEM_SEEN` (see §V-H) | Yes |
| S14 | Motion blur on the settling frames | N3 | `LOW_CONFIDENCE` or `MATCH`; never a swap accusation | Yes |
| S15 | Partial occlusion by existing basket contents | N4 | Refusal or `LOW_CONFIDENCE` | Yes |
| S16 | **Fully occluded substitution** (object hidden throughout) | A7 | **Cannot be resolved**; must remain unverified | **No — out of scope** |
| S17 | Dropped camera frames during the window | N5 | `RETRY` ("incomplete burst") | Yes |
| S18 | Camera stalled 1–4 s, heartbeats continuing | A8 | Verified units not invalidated; new work retries | Yes |
| S19 | Camera restart | A8 / N10 | Scene anomaly → mandatory reconciliation | Yes |
| S20 | Settlement delay beyond 0.90 s (bouncy item) | N6 | Baseline contamination → `NO_ITEM_SEEN` false reject | Yes (the failure is the measurement) |
| S21 | Scale drift across a session | N7 | Anchor advances on each attributed step; drift bounded by tolerance | Partially — drift compensation is not implemented |
| S22 | Cart pushed during placement | N8 | Firmware stability test withholds settlement | Yes |
| S23 | Cancel a placement mid-verification | N9 | No verdict published; no late approval | Yes |
| S24 | Duplicate / reordered / late settlement messages | N9 | Idempotent; exactly one verdict per `(τ,a)` | Yes |
| S25 | Authority restart with products in the basket | N10 | Non-`VERIFIED` units failed; empty-cart reconciliation required | Yes |
| S26 | PC verification service stopped | N10 | Heartbeat gap blocks checkout; no fake approval | Yes |
| S27 | Arduino unplugged | N10 | No synthetic samples; mass gates time out to `FAIL` | Yes |
| S28 | Items below the mass noise floor (< noise_g) | — | Mass gate cannot discriminate | **No — out of scope**; cf. the <20 g exemption in [8] |
| S29 | Loose produce / variable-weight goods | — | Not supported by the catalogue schema (`w_e` is a fixed gross mass) | **No — out of scope** |

Each scenario requires at least 30 genuine placements per SKU plus deliberately chosen confusable
pairs, over an empty and a partly filled basket, all relevant orientations, normal shopping speed and
the real store LAN. Thirty placements per cell is an initial bench set, **not** statistical
certification; with 30 trials and zero observed failures the one-sided 95 % Clopper–Pearson upper
bound on the failure rate is still approximately 9.5 %, which must be stated whenever a cell reads
"0 failures".

### E. Metrics

**TABLE X. Metrics, each with its denominator stated.**

| Metric | Definition | Denominator |
|---|---|---|
| False accept rate (FAR) | Adversarial attempts reaching `VERIFIED` | Adversarial attempts of that class (S3–S6, S10) |
| Honest false reject rate | Honest attempts whose first attempt is flagged | Honest attempts (S1, S9) |
| Retry rate | Attempts ending in `RETRY`/`UNAVAILABLE` | All attempts. **Reported separately from rejects**, since a retry is recoverable |
| Intervention rate | Sessions requiring an empty-cart reconciliation or staff action | Sessions |
| Exact basket correctness | Sessions whose final billed multiset equals ground truth | Sessions |
| Exact total correctness | Sessions whose final total equals the ground-truth total to the cent | Sessions |
| Substitution detection rate | S3/S4 attempts producing `SWAP_DETECTED` with the **correct** observed SKU | S3/S4 attempts |
| False accusation rate | Honest attempts producing `SWAP_DETECTED` | Honest attempts |
| Verification latency (p50 / p95) | `t_verdict − t_settled`, from Pi logs | Attempts producing a verdict |
| End-to-end latency (p50 / p95) | `t_verdict − t_scan` | As above. Reported **in addition to** the above, never instead |
| Achieved frame rate / gap distribution | From `manifest.json` realised counts and max gaps | Admissible + inadmissible bursts |
| Burst admissibility rate | Bursts passing (6)–(8) | Settlement events |
| Settlement delay `Δ_s` | `t_settled − t_impact` from an independent impact reference | Drops |
| Mass error | Measured delta minus reference-scale mass | Placements |
| Resource use | PC/Pi CPU %, RSS, PC inference time per ROI | Sampled |
| Network consumption | Bytes/s on the image topic, measured on the wire | Sampled |
| Risk–coverage curve | FAR against the fraction of attempts decided, as θ, μ, θ_swap vary | Attempts |

The last row is the honest way to report a system that may abstain [14], and the thresholds should be
reported as a curve rather than as a single operating point. Because cosine similarity is not a
calibrated probability [45], no row should be presented as a confidence or a probability of
correctness.

### F. Tuning/test separation and leakage controls

* Thresholds `θ, μ, θ_swap`, colour and aspect tolerances, and all burst timings are tuned on a
  **development** split and then frozen before the test campaign; the frozen values are reported.
* Reference photographs, tuning data and test data come from **disjoint capture sessions**, disjoint
  **physical units** of each product, and disjoint lighting conditions.
* Adjacent frames from the same burst must never be split across tuning and test — the unit of
  partition is the **capture session**, never the frame. Sixteen near-duplicate frames from one burst
  carry roughly one burst's worth of independent information (§V-G), so treating frames as independent
  samples would inflate every interval.
* Lookalike and equal-mass pairs are selected and held out *before* any tuning.
* Each reported figure states the number of sessions, attempts and physical units contributing to it,
  with Clopper–Pearson intervals for proportions.

### G. Instrumentation plan

An independent impact reference is required to measure `Δ_s`; a contact microphone or accelerometer on
the basket, logged on the Pi clock, is sufficient and does not need to be part of the product. Ground
truth for identity comes from the operator's log; the visual channel's own `manifest.json` provides
per-region diagnostics but must not be used as its own ground truth. Wire bandwidth is measured with a
packet counter on the PC interface, not inferred from (2).

---

## VIII. Results and Discussion

### A. What was actually measured

The only completed measurements are host-independent software checks, which the authors executed at
revision `28aa58d`.

**TABLE XI. Software-check results (executed; no hardware, no model download, no network request).**

| Check | Result |
|---|---|
| Environment | Windows 11, Python 3.14.7, OpenCV 5.0.0, NumPy 2.5.2 (a development host, **not** the ROS Jazzy target) |
| Source parse + package XML + interface parity + deployment boundaries | **PASS** — 85 Python sources parsed; both `smart_cart_interfaces` copies byte-identical; no boundary violation |
| Integration / regression suites (`tests/`) | **103 tests, OK** |
| Reference-handling suite (`pc/test_ai_references.py`) | **4 tests, OK** |
| Scripted verifier suite (`pc/test_verify.py`) | **ALL CHECKS PASSED** |

Of the 103 tests, 35 exercise the current burst pipeline directly (8 foreground-segmentation tests
using real OpenCV, 6 all-SKU/veto ranking tests, 18 node-level burst/cancellation/health tests, 3
camera-node tests), 26 exercise the Pi ledger, 11 the audit regressions, 4 the ROS adapters, 2 the
catalogue and serial contracts, 9 the matcher's database handling, and 4 the Pi scan/verdict binding.
**Twelve tests target retired components** (4 journey-window tests, 5 geometric-merge calibration
tests, 3 MOG2 motion tests) and are not evidence about the current pipeline.

### B. What these results do and do not establish

They establish that the source parses, that the two hosts' message contracts are identical, that the
deployment boundary holds, and that the implemented decision logic behaves as specified on constructed
inputs — including that an empty scene and a global lighting change never invoke the embedding
matcher, that a four-frame packet-loss gap returns `RETRY` rather than a decimated decision, that a
later confident swap vetoes an earlier match while every region is still evaluated, that a cancelled
or over-deadline job cannot publish an approval, and that a diagnostic disk failure cannot upgrade a
`MISMATCH` to a `MATCH`.

They establish **nothing** about: live DDS behaviour or wire latency (ROS callbacks are driven through
message-schema stubs and a patched clock); achieved camera frame rate; recognition accuracy on real
packaging; HX711 accuracy, linearity, creep or drift on a mounted basket; the distribution of `Δ_s`;
native `colcon` builds; Arduino compilation; or any security property. Neither `colcon` nor the
Arduino toolchain was available on the development host, so both native builds remain required
bring-up steps rather than completed validations. The test environment's OpenCV 5.0.0 also exceeds the
`>=4.10,<5` range the project pins for the ROS target, so the suites were exercised against a newer
DNN stack than the deployment one.

### C. Discussion: what the design buys, and what it costs

**Foreground-only inference removes a specific, identified failure mode and introduces another.** By
construction, no basket background reaches the network, so the matcher cannot score a scene against a
SKU and the "empty basket scores 0.666 against the target" pathology that motivated the design is
structurally impossible — a regression test pins exactly that case. The cost is that the method's
entire sensitivity now rests on the quality of one baseline frame. Baseline differencing cannot
distinguish a product from a hand holding it, cannot see a fully occluded object, and degrades under
shadows, reflections and any scene change between baseline and burst. Equations (12) and (14) convert
those degradations into refusals rather than into confident errors, which is the right safety
direction, but refusals have a shopper cost that is `[TO BE MEASURED]`.

**All-SKU competition is a contrastive device, not an identification claim.** Requiring the scanned
SKU to be top-1 with a margin is strictly stronger than an absolute threshold, and the margin
requirement is what makes a lookalike pair expensive to pass. But the open-set evidence from the
closest methodological comparator is sobering: a stronger pipeline than ours reports 67.5 %
Precision@1 at only 40 classes, with errors concentrated exactly on visually similar products [10].
We should therefore expect our top-1 ranking to be unreliable as a catalogue grows, and the veto
threshold `θ_swap = 0.70` to generate false accusations on honest lookalike placements. This is the
sharpest open risk in the design, it is measurable (TABLE X, "false accusation rate"), and it is the
reason the paper does not present the veto as a solved mechanism.

**Independence costs coverage and is the point.** Refusing to let a visual match offset a mass
failure guarantees that the attack class the mass channel *can* see is never argued away by the
channel that cannot. The symmetric cost is that two independent gates multiply their false-reject
rates, so B3 will have a strictly higher honest-retry rate than either B1 or B2. B4 exists in the
protocol precisely so that this trade can be measured rather than asserted.

**Weight-triggered selection is prior art; retrospective selection is the variation.** Triggering
detection on a stabilised weight change is already done [9]. What differs here is that the trigger does
not start a capture — it selects, from history, a window that *already contains* the event, along with
a baseline from before it, and refuses when that window is not complete. Section V-G shows that this
variation is what makes the configuration auditable: because the window is explicit and the manifest
records what was realised, the mismatch between the settlement timestamp and mechanical impact is
*visible in the data* instead of silently shaping the evidence.

**The settlement-timing result is the most consequential finding of this paper**, and it is analytical
rather than empirical. With the shipped firmware the system cannot observe the descent; it observes
the settled product, over near-duplicate frames, with roughly 0.30–0.40 s of decay budget before the
baseline is contaminated and the system emits a mislabelled false reject. Any deployment of this
configuration must measure `Δ_s` first. A reader who takes one engineering lesson from this manuscript
should take this one: in an event-triggered perception system, the *semantics* of the trigger
timestamp — stable-sample versus impact — silently determines what the evidence window contains.

---

## IX. Limitations and Threats to Validity

### A. No empirical validation of the primary claims

Every accuracy, latency, resource, cost and loss-reduction figure is pending. Static code inspection
is not proof of successful hardware operation, and a passing unit-test suite over constructed inputs
is not evidence about real packaging, real lighting or real middleware. The manuscript's contribution
is therefore a specification, an analysis and a protocol.

### B. A narrow visual match is not end-to-end theft prevention

The visual gate establishes, at best, that *some* foreground region in a settled-mass window was
consistent with the scanned SKU under a cosine threshold and a competitor margin. It does not
establish that no other object entered the basket, that the matched region is the object that caused
the mass change, or that an occluded exchange did not occur. Scenario S16 is explicitly out of scope
and must remain unresolved rather than being resolved optimistically.

### C. The two mass checks are not independent sensors

Equations (25) and (26) are computed by different processors from different baselines with different
code paths, which protects against a software fault or a stale expectation on one side. They read the
**same load cell through the same HX711**. A mechanical fault, a load path that bypasses the cell, a
calibration error or an ADC fault defeats both simultaneously. Describing this as sensor redundancy
would be wrong.

### D. Apparent size is not physical size

Equation (19) uses an image-plane aspect ratio from an uncalibrated monocular camera with no depth
channel. It cannot bound physical dimensions, and no claim in this paper depends on it beyond a weak
consistency filter.

### E. Single aggregate load cell

Concurrent placements cannot be attributed. The system flags them as ambiguous, which is correct but
is a *capability limit*, not a solution: a shopper who habitually inserts two items at once will
encounter repeated flags. Multiple cells are planned, not implemented.

### F. Security and payment

The cart LAN is assumed trusted; DDS security is not enabled, so topic injection by a host on the same
domain is not prevented. A single `/cart/vision_event` with a forged `(txn_id, attempt)` that happens
to match a pending unit's barcode would be accepted as a camera verdict. Transaction and attempt
binding provides *replay* resistance (a completed key is remembered and a verdict for a stale attempt
is dropped) but not authentication. On payment: the system generates a revision-gated UPI deep-link QR
[56]. **Generating a payment request is not confirmed settlement.** A displayed static QR cannot
revoke a screenshot already taken and cannot prove that money moved. Unattended commercial checkout
additionally requires provider-side order authorisation and a confirmed-settlement webhook, neither of
which exists in this code.

### G. Thresholds are unvalidated defaults

The nine decision thresholds in TABLE VI were chosen during development. None is derived from an
operating-characteristic analysis on held-out data. Reporting them as a frozen operating point without
a risk–coverage curve would overstate their status.

### H. Catalogue and generalisation scope

The catalogue schema requires a single fixed gross mass per SKU, which excludes loose produce and
variable-weight goods (S29), and the mass channel cannot discriminate items below the noise gate
(S28). Reference photographs must be product crops in the deployment camera's own domain; references
captured on a different camera measure the domain gap rather than the method. A database built with
one embedding backend is meaningless to another, which the code enforces by refusing a mismatched
backend stamp.

### I. Internal validity

The settlement-timing analysis assumes the firmware constants in TABLE V, that HX711 sampling is
gated at ~100 ms, and that serial transport latency is small relative to 0.5 s. The first two are read
from source; the third is an assumption pending measurement. The bandwidth and memory figures (1)–(2)
are arithmetic from the configuration and exclude all protocol overhead.

### J. External validity

A single prototype cart, one camera geometry, one mounting stiffness, one LAN and one small catalogue
cannot support claims about store-scale behaviour. Results from this protocol will characterise *this
cart*. Catalogue growth, in particular, is expected to degrade the all-SKU ranking [10], so any
reported operating point is specific to the catalogue size at which it was measured.

### K. Construct validity

The metrics in TABLE X measure billing correctness and gate behaviour. They do not measure shrinkage
reduction, which depends on shopper behaviour, store process and deterrence, and which cannot be
inferred from a bench matrix. No claim about loss reduction is made.

### L. Literature-review completeness

The review draws on a curated pack of 85 resources, of which 10 were read in full. It is **not** a
systematic review: no protocol-registered database query, date range, screening log or
forward/backward citation saturation was performed. Items reviewed only at metadata or abstract level
are labelled as such in TABLE I and in the disposition supplement, and no claim in this paper depends
on an unread full text. Where supplied papers contained internal inconsistencies, those were recorded
(Sections II-A, II-B, II-C) and their citation mappings were not reused.

---

## X. Conclusion and Future Work

We have specified NXTCart, a barcode-first smart shopping cart in which a scanned product's identity
is checked by two independent, conjunctive gates: an independently recomputed settled-mass comparison
on an Arduino/HX711, and a foreground-only visual verification on a separate host over ROS 2. We do
not claim the barcode/weight/image combination, weight reconciliation, or weight-triggered inference
as novel; close prior art exists for each. The design choices we do document and defend are
mechanical: retrospective selection of a dense, gap-checked evidence window from a bounded
source-timestamped history around a settled-mass event, together with a pre-entry baseline; embedding
only connected foreground regions so that no scene background ever reaches the network; scoring every
region against every registered SKU so that a confident alternate product vetoes a matching region
elsewhere in the same burst; binding every verdict to a transaction and attempt; and abstaining when
the evidence window is incomplete.

The paper's substantive analytical result is that these mechanisms are only as good as the semantics
of their trigger. Because the settlement timestamp marks a six-sample stability decision rather than a
mechanical impact, the shipped configuration cannot observe the product in descent and is
self-consistent only while the impact-to-settlement delay remains between 0.40 s and 0.90 s, leaving
roughly 0.30–0.40 s of mechanical decay budget before the selected baseline is contaminated by the
product itself and the system emits a mislabelled false reject. Measuring that delay distribution is
the first required step of any deployment, and the diagnostic manifests make it directly checkable.

We also report, as a verified fact, that the software checks pass at the stated revision — 103
integration and regression tests, interface parity between hosts, and an enforced deployment boundary
— and we state plainly that this establishes none of the system's accuracy, timing or security
properties.

Future work falls into three tiers, deliberately separated by evidential status.

*Required before any accuracy claim:* execute the protocol of Section VII; measure `Δ_s` with an
independent impact reference and re-tune `δ_pre`, `δ_base` and `T_buf` together, or publish a distinct
impact timestamp; measure achieved frame rate, gap distribution and wire bandwidth; replace the
fixed thresholds with a reported risk–coverage curve on held-out confusable pairs; complete native
`colcon` and Arduino builds and live DDS acceptance.

*Natural extensions of the implemented design:* calibrated confidence in place of raw cosine scores
[45], [14]; stronger frozen backbones or vision-language retrieval as drop-in replacements for the
feature extractor [38], [39], [40]; a diagnostic-manifest-driven regression corpus so threshold changes
can be replayed offline; drift compensation in the mass channel along the lines of [8]; and provider-side
payment authorisation with confirmed settlement [56].

*Proposed but unimplemented, and not to be described otherwise:* monitored-aperture light curtains,
multiple load cells for position-resolved mass, IMU compensation for cart motion, continuous basket
reconciliation, in-store navigation, and inventory forecasting [30]. These appear in the project's
design material as planned work and have no implementation evidence in the code examined here.

---

## Acknowledgment

[ACKNOWLEDGMENT PLACEHOLDER — funding sources, grant numbers, institutional support, equipment loans,
and non-author contributors. The authors thank [NAMES] for [CONTRIBUTION]. Remove this section if not
applicable; do not list any funder that has not approved acknowledgment.]

---

## References

[1] B. Santra and D. P. Mukherjee, "A comprehensive survey on computer vision based approaches for automatic identification of products in retail store," *Image and Vision Computing*, vol. 86, pp. 45–63, 2019, doi: 10.1016/j.imavis.2019.03.005.

[2] Y. Wei, S. Tran, S. Xu, B. Kang, and M. Springer, "Deep learning for retail product recognition: Challenges and techniques," *Computational Intelligence and Neuroscience*, vol. 2020, pp. 1–23, 2020, doi: 10.1155/2020/8875910.

[3] R. Oucheikh, T. Pettersson, and T. Löfström, "Product verification using OCR classification and Mondrian conformal prediction," *Expert Systems with Applications*, vol. 188, p. 115942, 2022, doi: 10.1016/j.eswa.2021.115942.

[4] Instacart, "Caper Carts: Official product overview." [Online]. Available: https://company.instacart.com/enterprise-platform/connected-stores/caper-carts (accessed Oct. 12, 2026). *Vendor product claim; not peer-reviewed evidence.*

[5] Amazon, "5 ways the newest Dash Cart can save time and money," 2026. [Online]. Available: https://www.aboutamazon.com/news/retail/amazon-redesigned-dash-cart-whole-foods-market (accessed Oct. 12, 2026). *Vendor product claim; not peer-reviewed evidence.*

[6] V. N. Prithvish, S. Agrawal, and J. S. R. Alex, "An IoT-based smart shopping cart using the contemporary barcode scanner," in *Intelligent Embedded Systems*, Lecture Notes in Electrical Engineering 492, 2018, pp. 45–58, doi: 10.1007/978-981-10-8575-8_6.

[7] U. Gangwal, S. Roy, and J. Bapat, "Smart shopping cart for automated billing purpose using wireless sensor networks," in *SENSORCOMM 2013*, IARIA, 2013, pp. 168–172. [Online]. Available: https://personales.upv.es/thinkmind/SENSORCOMM/SENSORCOMM_2013/sensorcomm_2013_7_30_10155.html

[8] M. Desai, B. N. K., M. Shirol, K. A. Varun, and C. J., "A weight-reconciliation algorithm for fraud detection in smart shopping carts," in *2026 4th Int. Conf. Knowledge Engineering and Communication Systems (ICKECS)*, 2026, pp. 1–4, doi: 10.1109/ICKECS70176.2026.11527873.

[9] J. Zhang, Z. Xu, C. Liang, and Y. Zhu, "Intelligent shopping cart product recognition system based on computer vision and multi-sensor fusion," in *2025 5th Int. Conf. Communication Technology and Information Technology (ICCTIT)*, 2025, pp. 249–253, doi: 10.1109/ICCTIT68197.2025.11406732.

[10] Z. Al Adzani Hidayat, H. F. Ramadhan, P. Hidayatullah, and N. Syakrani, "A few-shot learning pipeline for retail product recognition using object detection and metric embeddings," in *2025 8th Int. Conf. Information and Communications Technology (ICOIACT)*, 2025, pp. 42–47, doi: 10.1109/ICOIACT67584.2025.11344991.

[11] B. Ciapas and P. Treigys, "Centre-loss—A preferred class verification approach over sample-to-sample in self-checkout products datasets," *IET Computer Vision*, vol. 18, no. 7, pp. 1004–1016, 2024, doi: 10.1049/cvi2.12302.

[12] M. Sandler, A. Howard, M. Zhu, A. Zhmoginov, and L.-C. Chen, "MobileNetV2: Inverted residuals and linear bottlenecks," in *2018 IEEE/CVF Conf. Computer Vision and Pattern Recognition (CVPR)*, 2018, pp. 4510–4520, doi: 10.1109/CVPR.2018.00474.

[13] S. Macenski, T. Foote, B. Gerkey, C. Lalancette, and W. Woodall, "Robot Operating System 2: Design, architecture, and uses in the wild," *Science Robotics*, vol. 7, no. 66, 2022, doi: 10.1126/scirobotics.abm6074.

[14] Y. Geifman and R. El-Yaniv, "Selective classification for deep neural networks," in *Advances in Neural Information Processing Systems 30*, 2017. [Online]. Available: https://arxiv.org/abs/1705.08500

[15] M. Shahroz, M. F. Mushtaq, M. Ahmad, S. Ullah, A. Mehmood, and G. S. Choi, "IoT-based smart shopping cart using radio frequency identification," *IEEE Access*, vol. 8, pp. 68426–68438, 2020, doi: 10.1109/ACCESS.2020.2986681.

[16] P. Chandrasekar and T. Sangeetha, "Smart shopping cart with automatic billing system through RFID and ZigBee," in *Int. Conf. Information Communication and Embedded Systems (ICICES2014)*, 2014, pp. 1–4, doi: 10.1109/ICICES.2014.7033996.

[17] P. A. Jeyanthy, S. R. Mohamed, M. Alarfaj, S. S. Reddy, and K. S. Jenin, "Design and development of a smart shopping cart system," in *2022 3rd Int. Conf. Intelligent Computing Instrumentation and Control Technologies (ICICICT)*, 2022, pp. 184–188, doi: 10.1109/ICICICT54557.2022.9917860.

[18] S. Sakthivel, A. R. R. K., S. Sai B., V. K. K. M., and G. Kumar C., "AIoT-based smart cart system," in *2022 Int. Conf. Smart Technologies and Systems for Next Generation Computing (ICSTSN)*, 2022, pp. 1–6, doi: 10.1109/ICSTSN53084.2022.9761346.

[19] S. Karjol, A. K. Holla, C. B. Abhilash, P. V. Amrutha, and Y. V. Manohar, "An IoT based smart shopping cart for smart shopping," in *Cognitive Computing and Information Processing*, Communications in Computer and Information Science 801, 2018, pp. 373–385, doi: 10.1007/978-981-10-9059-2_33. *Cited with the publisher's corrected five-author attribution.*

[20] R. Li, T. Song, N. Capurso, J. Yu, J. Couture, and X. Cheng, "IoT applications on secure smart shopping system," *IEEE Internet of Things Journal*, vol. 4, no. 6, pp. 1945–1954, 2017, doi: 10.1109/JIOT.2017.2706698.

[21] B. K. Rajithkumar, G. M. Deepak, B. V. Uma, B. N. Hadimani, A. R. Darshan, and C. R. Kamble, "Design and development of weight sensors based smart shopping cart and rack system for shopping malls," *Materials Today: Proceedings*, vol. 5, no. 4, pp. 10814–10820, 2018, doi: 10.1016/j.matpr.2017.12.367.

[22] A. Yewatkar, F. Inamdar, R. Singh, Ayushya, and A. Bandal, "Smart cart with automatic billing, product information, product recommendation using RFID & ZigBee with anti-theft," *Procedia Computer Science*, vol. 79, pp. 793–800, 2016, doi: 10.1016/j.procs.2016.03.107.

[23] B. Chaure and P. Jain, "Development of e-shopping cart with theft control mechanism: No queue," in *2016 Int. Conf. Emerging Technological Trends (ICETT)*, 2016, pp. 1–5, doi: 10.1109/ICETT.2016.7873753.

[24] N. Ragesh, B. Giridhar, D. Lingeshwaran, P. Siddharth, and K. P. Peeyush, "Deep learning based automated billing cart," in *2019 Int. Conf. Communication and Signal Processing (ICCSP)*, 2019, pp. 779–782, doi: 10.1109/ICCSP.2019.8697995.

[25] T. W. Alessa, F. Ahmed Alfarhan, F. K. Bugis, A. Abdulhadi Aldawood, S. A. Alhuwaidi, and A. Abul Hussain, "Smart shopping cart with machine learning, navigation, and weighing technologies," in *2024 6th Int. Symp. Advanced Electrical and Communication Technologies (ISAECT)*, 2024, pp. 1–6, doi: 10.1109/ISAECT64333.2024.10799859.

[26] A. Naithani, T. S. Rajpal, and V. Mistry, "TAV-Cart: Transaction assistance and validation cart system for effortless shopping and checkout," in *2024 Int. Conf. Advances in Computing, Communication and Materials (ICACCM)*, 2024, pp. 1–6, doi: 10.1109/ICACCM61117.2024.11059075.

[27] A. Prabhath, A. Anoop, and V. Sureshkumar, "Multi-modal product recognition and in-store navigation using an intelligent shopping cart," in *2026 5th Int. Conf. Computer Networks, Big Data and IoT (ICCBI)*, 2026, pp. 1241–1245, doi: 10.1109/ICCBI68589.2026.11619726.

[28] M. A. Sarwar, Y.-A. Daraghmi, K.-W. Liu, H.-C. Chi, T.-U. Ik, and Y.-L. Li, "Smart shopping carts based on mobile computing and deep learning cloud services," in *2020 IEEE Wireless Communications and Networking Conf. (WCNC)*, 2020, pp. 1–6, doi: 10.1109/WCNC45663.2020.9120574.

[29] Y. Berdaliyev and A. P. James, "RFID-cloud smart cart system," in *2016 Int. Conf. Advances in Computing, Communications and Informatics (ICACCI)*, 2016, pp. 2346–2352, doi: 10.1109/ICACCI.2016.7732405.

[30] M. I. Zulfiqar, A. Khalid, A. Siddig, M. J. Nawaz, and S. Saay, "AI-driven smart shopping carts with real-time tracking and inventory forecasting for enhanced retail efficiency," *IEEE Access*, vol. 13, pp. 55576–55585, 2025, doi: 10.1109/ACCESS.2025.3553854.

[31] L. H. Pham, D. Nguyen-Ngoc Tran, H.-H. Nguyen, T. H.-P. Tran, H.-J. Jeon, H.-M. Jeon, and J. W. Jeon, "DeepACO: A robust deep learning-based automatic checkout system," in *2022 IEEE/CVF Conf. Computer Vision and Pattern Recognition Workshops (CVPRW)*, 2022, pp. 3106–3113, doi: 10.1109/CVPRW56347.2022.00350.

[32] X.-S. Wei, Q. Cui, L. Yang, P. Wang, L. Liu, and J. Yang, "RPC: A large-scale and fine-grained retail product checkout dataset," *Science China Information Sciences*, vol. 65, no. 9, 2022, doi: 10.1007/s11432-022-3513-y.

[33] E. Goldman, R. Herzig, A. Eisenschtat, J. Goldberger, and T. Hassner, "Precise detection in densely packed scenes," in *2019 IEEE/CVF Conf. Computer Vision and Pattern Recognition (CVPR)*, 2019, pp. 5222–5231, doi: 10.1109/CVPR.2019.00537.

[34] M. Klasson, C. Zhang, and H. Kjellström, "A hierarchical grocery store image dataset with visual and semantic labels," in *2019 IEEE Winter Conf. Applications of Computer Vision (WACV)*, 2019, pp. 491–500, doi: 10.1109/WACV.2019.00058.

[35] Y. Yao, X. Tian, Z. Tang, S. Biswas, H. Lei, T. Gedeon, and L. Zheng, "Training with product digital twins for AutoRetail checkout," arXiv:2308.09708, 2023. [Online]. Available: https://arxiv.org/abs/2308.09708

[36] J.-Y. Jeon, S.-W. Kang, H.-J. Lee, and J.-S. Kim, "A retail object classification method using multiple cameras for vision-based unmanned kiosks," *IEEE Sensors Journal*, vol. 22, no. 22, pp. 22200–22209, 2022, doi: 10.1109/JSEN.2022.3210699.

[37] I. Baz, E. Yoruk, and M. Cetin, "Context-aware hybrid classification system for fine-grained retail product recognition," in *2016 IEEE 12th Image, Video, and Multidimensional Signal Processing Workshop (IVMSP)*, 2016, pp. 1–5, doi: 10.1109/IVMSPW.2016.7528213.

[38] A. Radford, J. W. Kim, C. Hallacy, A. Ramesh, G. Goh, S. Agarwal, G. Sastry, A. Askell, P. Mishkin, J. Clark, G. Krueger, and I. Sutskever, "Learning transferable visual models from natural language supervision," in *Proc. 38th Int. Conf. Machine Learning (ICML)*, 2021. [Online]. Available: https://proceedings.mlr.press/v139/radford21a.html

[39] M. Oquab *et al.*, "DINOv2: Learning robust visual features without supervision," arXiv:2304.07193, 2023. [Online]. Available: https://arxiv.org/abs/2304.07193

[40] E. G. Maminta and R. O. Atienza, "What matters for grocery product retrieval with open source vision language models," arXiv:2605.18029, 2026. [Online]. Available: https://arxiv.org/abs/2605.18029 *Cited as the verified arXiv preprint version; no final proceedings record is claimed.*

[41] J. Falcão, C. Ruiz, S. Pan, H. Y. Noh, and P. Zhang, "FAIM: Vision and weight sensing fusion framework for autonomous inventory monitoring in convenience stores," *Frontiers in Built Environment*, vol. 6, 2020, doi: 10.3389/fbuil.2020.568372.

[42] C. Ruiz, J. Falcao, S. Pan, H. Y. Noh, and P. Zhang, "AIM3S: Autonomous inventory monitoring through multi-modal sensing for cashier-less convenience stores," in *Proc. 6th ACM Int. Conf. Systems for Energy-Efficient Buildings, Cities, and Transportation*, 2019, pp. 135–144, doi: 10.1145/3360322.3360834.

[43] D. L. Hall and J. Llinas, "An introduction to multisensor data fusion," *Proceedings of the IEEE*, vol. 85, no. 1, pp. 6–23, 1997, doi: 10.1109/5.554205.

[44] B. Khaleghi, A. Khamis, F. O. Karray, and S. N. Razavi, "Multisensor data fusion: A review of the state-of-the-art," *Information Fusion*, vol. 14, no. 1, pp. 28–44, 2013, doi: 10.1016/j.inffus.2011.08.001.

[45] C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, "On calibration of modern neural networks," in *Proc. 34th Int. Conf. Machine Learning (ICML)*, 2017. [Online]. Available: https://proceedings.mlr.press/v70/guo17a.html

[46] Open Robotics, "ROS 2 Jazzy: About quality of service settings." [Online]. Available: https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html (accessed Oct. 12, 2026).

[47] J. Redmon, S. Divvala, R. Girshick, and A. Farhadi, "You only look once: Unified, real-time object detection," in *2016 IEEE Conf. Computer Vision and Pattern Recognition (CVPR)*, 2016, pp. 779–788, doi: 10.1109/CVPR.2016.91.

[48] A. Bewley, Z. Ge, L. Ott, F. Ramos, and B. Upcroft, "Simple online and realtime tracking," in *2016 IEEE Int. Conf. Image Processing (ICIP)*, 2016, pp. 3464–3468, doi: 10.1109/ICIP.2016.7533003.

[49] N. Wojke, A. Bewley, and D. Paulus, "Simple online and realtime tracking with a deep association metric," in *2017 IEEE Int. Conf. Image Processing (ICIP)*, 2017, pp. 3645–3649, doi: 10.1109/ICIP.2017.8296962.

[50] Avia Semiconductor, "HX711: 24-bit analog-to-digital converter for weigh scales," datasheet. [Online]. Available: https://cdn.sparkfun.com/assets/b/f/5/a/e/hx711F_EN.pdf (accessed Oct. 12, 2026).

[51] B. Necula and contributors, "HX711 Arduino library." [Online]. Available: https://github.com/bogde/HX711 (accessed Oct. 12, 2026).

[52] Arduino, "A guide to EEPROM." [Online]. Available: https://github.com/arduino/docs-content/blob/main/content/learn/03.programming/07.eeprom-guide/eeprom-guide.md (accessed Oct. 12, 2026).

[53] Natural History Museum and contributors, "pyzbar: Barcode and QR decoding." [Online]. Available: https://github.com/NaturalHistoryMuseum/pyzbar (accessed Oct. 12, 2026).

[54] OpenCV, "Deep learning in OpenCV." [Online]. Available: https://github.com/opencv/opencv/wiki/Deep-Learning-in-OpenCV (accessed Oct. 12, 2026).

[55] R. Szeliski, *Computer Vision: Algorithms and Applications*, 2nd ed. Springer, 2022, doi: 10.1007/978-3-030-34372-9.

[56] National Payments Corporation of India, "UPI frequently asked questions." [Online]. Available: https://www.npci.org.in/what-we-do/upi/faqs (accessed Oct. 12, 2026).
