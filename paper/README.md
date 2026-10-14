# NXTCart research-paper deliverables

Produced 12–13 October 2026 against repository revision
`28aa58d3ceff6a7d03a2d208d9d4065606af85f8` (11 October 2026, branch `main`).

## Files

| File | What it is |
|---|---|
| [`NXTCart_Manuscript.md`](NXTCart_Manuscript.md) | **The manuscript.** Complete, with abstract, keywords, 11 tables, 29 equations, 4 algorithms, 56 IEEE-numbered references. Readable as-is. |
| [`NXTCart_IEEEtran.tex`](NXTCart_IEEEtran.tex) | Standalone IEEEtran conference source. Self-contained (inlined `thebibliography`, placeholder figure boxes), so it needs no `.bib` run and no image assets. **Compilation NOT verified** — see below. |
| [`nxtcart_cited.bib`](nxtcart_cited.bib) | BibTeX for exactly the 56 cited sources, in citation order, keyed `NXTCartR01`…`NXTCartR85`. For reference-manager import. |
| [`NXTCart_Figures_Tables_Equations.md`](NXTCart_Figures_Tables_Equations.md) | Editable artifacts: 6 figure specifications (Mermaid + TikZ/ASCII coordinates), all captions, LaTeX equation source, LaTeX `algorithmic` pseudocode, table-source index, and three empty results skeletons (Tables XII–XIV). |
| [`NXTCart_S1_Resource_Disposition.md`](NXTCart_S1_Resource_Disposition.md) | Disposition for all **85** catalogue resources: 56 cited (with IEEE number and role), 29 excluded with reasons. Includes the RP1–RP10 → Rnn map, review-depth tally, deduplication result, and citation-quality notes for RP4–RP10. |
| [`NXTCart_S2_Missing_Measurements.md`](NXTCart_S2_Missing_Measurements.md) | Pre-submission checklist: 10 administrative items, 20 blocking measurements, 11 deployment items, 14 facts that rot if code changes, 6 analytical values that must stay labelled, and the figures that must stay attributed. |
| [`NXTCart_S3_Claim_Evidence.md`](NXTCart_S3_Claim_Evidence.md) | Claim-to-evidence map: 40 implementation claims → source file + test, 13 analytical claims → derivation, 13 novelty claims → constraining prior art, 16 claims deliberately **not** made, and the completed-measurement rows. |
| [`tools/make_disposition.py`](tools/make_disposition.py) | Generates the S1 tables directly from `resource_catalogue.json`, so bibliographic details cannot drift from the source of record. |
| [`tools/audit.py`](tools/audit.py) | Consistency audit: reference gaplessness, citation resolution, equation/table numbering, bib↔manuscript↔disposition agreement, obsolete-phrase check, placeholder visibility. |

## Reproduce the checks

```bash
cd paper && py -I tools/audit.py
```

Last run: **23 checks, 0 failures.** It verifies 56 gapless references all cited and all resolving,
equations 1–29 sequential, tables I–XI sequential with every in-text reference resolving, the bib and
disposition sets agreeing exactly with the manuscript, all 85 catalogue refs dispositioned exactly
once, and that the obsolete-architecture phrases appear only inside disclaiming sentences.

```bash
cd paper && py -I tools/make_disposition.py \
  ../../NXTCart-Cam/research/resource_catalogue.json /tmp/rows.md
```

## Status disclosures

* **LaTeX compilation was not verified.** No TeX distribution (`pdflatex`, `xelatex`, `lualatex`,
  `latexmk`) is installed on the authoring host. The `.tex` is written to be self-contained and its
  header states this. Build with `pdflatex NXTCart_IEEEtran.tex` twice, with `IEEEtran.cls` present.
* **The only completed measurements** are the software checks in §VIII-A, which were executed in this
  pass: 85 sources parsed, interface parity, deployment boundary, 103 + 4 unit tests and the scripted
  verifier suite, all passing on Windows 11 / Python 3.14.7 / OpenCV 5.0.0 / NumPy 2.5.2. That host is
  **not** the ROS Jazzy target and its OpenCV exceeds the project's pinned `>=4.10,<5`.
* **No hardware result exists.** 13 `[TO BE MEASURED]` / `[TO BE RECORDED]` markers remain in the
  manuscript by design.
* **Architecture was resolved from the launched source**, not from the prose documentation:
  `pc/config/verification.yaml`, both launch files, and
  `vision_verify_node.py` / `burst.py` / `local_matcher.py`. The documentation supersession chain
  (`SYSTEM_SETUP.md` → `LENIENT_VISION_SETUP.md` → `WEIGHT_TRIGGERED_VISION.md`) was followed; the
  stale README and setup-guide passages are named as such in §VI-G and S2 §E.

## Length: fitting the 8–10 page target

The manuscript currently runs **≈10,700 words of prose plus 11 tables and 6 figures**, which in
IEEEtran two-column is roughly **12–14 pages** — over the 8–10 page target. It is delivered complete
rather than pre-cut, because which rigour to shed is an editorial call. Apply these in order; each
line gives the realistic saving.

| # | Cut | Saving | Cost |
|---|---|---|---|
| 1 | Move TABLE I (related work) to the supplement, keep a 5-row version covering [9], [8], [3], [10] and NXTCart | ≈1.0 pg | Reviewers lose the full comparison at a glance |
| 2 | Move TABLE IX (scenarios) to the supplement, keep the 8 adversarial rows | ≈0.7 pg | Nuisance coverage less visible |
| 3 | Compress §II-A/§II-B/§II-C from ~2,400 to ~1,200 words; keep [9], [8], [3], [10], [26] in prose and push the rest to TABLE I | ≈1.3 pg | Least costly large cut |
| 4 | Drop Algorithm 4 (checkout predicate) — the nine conditions are already prose in §IV-D | ≈0.4 pg | None material |
| 5 | Merge §IX-I/J/K (internal/external/construct validity) into one paragraph | ≈0.4 pg | Threats less itemised |
| 6 | Move TABLE III (ROS contract) and TABLE VI (parameters) to the supplement, keeping only the burst parameters inline | ≈0.9 pg | Reproducibility detail moves one click away |
| 7 | Drop Fig. 3 (sequence) — Fig. 1 plus §V-B covers the flow | ≈0.4 pg | Flow harder to follow |

Cuts 1–4 reach ≈9–10 pages while preserving §V-G (the settlement-timing analysis), §VII (the
protocol) and §IX-A/B/C (the three load-bearing limitations). **Do not cut:** the Document Status
block, the §I-B non-novelty disclaimers, §V-G, or any `[TO BE MEASURED]` marker — each is what keeps
the paper's claims proportionate to its evidence.

## What the paper argues, in one paragraph

Barcode + weight + vision carts, weight reconciliation, and weight-triggered inference are all prior
art, and the paper says so explicitly in §I-B rather than claiming them. What it documents and defends
are four mechanisms — retrospective selection of a dense, gap-checked evidence window from a bounded
timestamped frame history around a *settled-mass* event; embedding only pre-entry-baseline foreground
regions so no scene background reaches the network; all-SKU competition with a burst-level
substitution veto; and independent, non-fused, conjunctive gates bound to a transaction and attempt —
plus one analytical result: because the settlement timestamp marks a six-sample stability decision
rather than mechanical impact, the shipped configuration cannot observe the product in descent and is
self-consistent only while the impact-to-settlement delay stays between 0.40 s and 0.90 s, leaving
roughly 0.30–0.40 s of mechanical decay budget before the chosen baseline is contaminated by the
product itself and the system emits a mislabelled false reject. Measuring that delay is the first
required step of any deployment.
