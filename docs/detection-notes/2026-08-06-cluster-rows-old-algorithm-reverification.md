# Old-algorithm reverification report: does any of the original 4 cited cases still justify the Task-1 `cluster_rows` fix under the current system?

> **Archived as written on 06/08/2026, TRƯỚC khi revert.** "Currently committed", "hiện tại", hay
> các cụm tương tự trong báo cáo này đều chỉ trạng thái tại thời điểm viết (commit `4a9ffed`,
> thuật toán row-mean + span-cap) — KHÔNG phải trạng thái hiện tại của `row_clustering.py`. File
> này đã được revert về thuật toán gốc ngay trong chính commit đã lưu báo cáo này (xem
> `docs/detection-notes/detection-log.md`, mục 06/08/2026).

Status: **DONE** (no "could not verify" gaps — every number below is real command
output from a fresh run this session, no reused approximate numbers).

No tracked files were modified. `git status --porcelain` at the end of this
investigation shows only the pre-existing untracked symlinks (`.venv-e2e`,
`runs`, `docs/superpowers`, `data/scan_viz/input/input_crop`) plus the new
`data/scan_viz/diagnostic_{row4,row9,haohao_old,haohao_new,yakult_old,yakult_new}/annotated.jpg`
outputs — all gitignored (`data/scan_viz/*`, same as the prior diagnostic
report confirmed). `src/pipeline/row_clustering.py` was swapped to the
pre-`4a9ffed` version and back **5 times** during this investigation (once per
script run that needed OLD behavior); each restore was verified immediately
with `git diff --stat src/pipeline/row_clustering.py` (empty) and a final
`git diff src/pipeline/row_clustering.py | wc -l` → `0` at the end. The file
is at the exact `4a9ffed`-committed state now.

## Environment / methodology

- Weights: `runs/detect/runs/train_1a/n_2000/weights/best.pt`
- Python: `.venv-e2e/bin/python3`
- OLD algorithm source: `git show 4a9ffed~1:src/pipeline/row_clustering.py`
  (single-linkage, compares to `rows[-1][-1]` only). NEW algorithm source:
  the currently committed file (`4a9ffed`, row-mean + span-cap check,
  `max_span_multiplier=2.0` default).
- All pipeline stages reproduced exactly as `src/pipeline/scan.py::run_scan()`
  and `scripts/verify_cluster_rows_fix.py` run them: `detect_1a` →
  `adaptive_tolerances()` → `merge_adjacent_fragments()` →
  [`cluster_rows` via `filter_anomalous_boxes`] → `filter_contained_boxes` →
  `detect_gaps` (also via `cluster_rows`).
- Throwaway scripts (not committed, not part of the repo), all under
  `/private/tmp/claude-501/-Users-realzoey-Project-shelf-stock-monitoring/7cd2c751-e4f5-4ff0-81c4-7a20c64b284a/scratchpad/`:
  `inv1_test3_old_rows.py`, `inv1_context.py`, `inv1_full_rows_1950_2750.py`,
  `inv2_haohao.py`, `inv2_contained.py`.
- Annotated images produced by the existing, unmodified
  `scripts/verify_cluster_rows_fix.py --out ...` (per-region `--check-region`
  flags), run once with the committed (NEW) `row_clustering.py` and once with
  the OLD version swapped in, for the full pipeline renders (Investigations
  2 and 3).

---

## Investigation 1: old row 4 and old row 9 (test3.HEIC)

### Fresh reproduction of OLD `cluster_rows` on `boxes_merged`

```
raw=54 merged=54 tol=23.4291 ygap=4.5106
total rows: 23

candidates with span > tolerance (23.4291):
  row 4: n=4 yc=(1398.0-1424.6) span=26.6 (1.13x tolerance)
  row 5: n=5 yc=(1456.5-1500.3) span=43.8 (1.87x tolerance)
  row 9: n=3 yc=(2314.3-2343.1) span=28.8 (1.23x tolerance)
  row 18: n=12 yc=(3242.5-3338.5) span=96.0 (4.10x tolerance)
```

Matches Task 3's previously-reported numbers exactly — re-derived fresh, not
reused.

**Old row 4** (n=4, real box tuples, fresh run):
```
(2032.8,1008.9,2285.4,1787.2) yc=1398.0 w=252.6 h=778.3
(1753.6,1011.9,2018.5,1804.8) yc=1408.3 w=264.9 h=792.9
(1482.3,1028.4,1742.9,1810.1) yc=1419.2 w=260.6 h=781.6
(2302.6,1081.2,2563.4,1768.0) yc=1424.6 w=260.9 h=686.8
```
Bounding region: `1482.3,1008.9,2563.4,1810.1`

**Old row 9** (n=3, real box tuples, fresh run):
```
(0.0,2200.4,116.7,2428.3)     yc=2314.3 w=116.7 h=228.0   -- "r9_a"
(127.4,2039.4,984.8,2614.6)   yc=2327.0 w=857.5 h=575.2   -- "r9_b"
(1036.5,2005.7,1882.1,2680.6) yc=2343.1 w=845.6 h=675.0   -- "r9_c"
```
Bounding region: `0.0,2005.7,1882.1,2680.6`

### Does the NEW (current, committed) algorithm split either row?

Ran the current committed `cluster_rows` on the same `boxes_merged` and
located every one of the 4+3 boxes above by exact coordinate match (tolerance
0.5px):

```
old row 4 boxes -> NEW row index 4 (all 4)
old row 9 boxes -> NEW row index 10 (all 3)
```

Both land in the **same single NEW row**, with **identical membership** to the
OLD row (verified by printing the full NEW-row-4 and NEW-row-10 contents —
byte-identical box lists to old row 4 and old row 9 above). **Neither row is
split by the fix.** This is unlike old row 5 and old row 18 (already reported
by Task 3/the diagnostic as over-fragmented by the NEW mean-check).

### Physical structure

**Row 4**: x-ranges 1482-1743 / 1754-2019 / 2033-2285 / 2303-2563 — four
non-overlapping, side-by-side x-ranges. Annotated image
(`data/scan_viz/diagnostic_row4/annotated.jpg`, current/NEW algorithm,
`--check-region 1482.3,1008.9,2563.4,1810.1`) visually confirms this is the
top shelf's row of Betagen/Lotha-Milk fermented-milk bottles standing side by
side — one real physical shelf row, matching Task 3's prior visual
confirmation, re-verified here on a fresh render.
`scripts/verify_cluster_rows_fix.py`'s own check-region output:
`PHANTOM GAP STILL PRESENT (1 overlapping gap(s))` — the reported gap is
`(1733.8, 1011.0, 2027.2, 1351.7)`, one of the two byte-identical pre/post-fix
gaps already documented in the prior diagnostic report; it does not indicate
a row-4-specific issue.

**Row 9**: x-ranges 0-117 (r9_a) / 127-985 (r9_b) / 1036-1882 (r9_c). Annotated
image (`data/scan_viz/diagnostic_row9/annotated.jpg`, current algorithm,
`--check-region 0.0,2005.7,1882.1,2680.6`) shows this region is the Yakult
5-pack shelf (2nd shelf from top in the crop: pink Yakult Hương Đào packs and
blue Yakult Light packs). Check-region output: `clear (0 overlapping gap(s))`
— no phantom gap in this region under the current algorithm.

Fresh containment check (this session, `containment_ratio` from
`src.detection.benchmark.metrics`) of `r9_a` against every merged box below
yc=2350 with x1<200 in the same image:
```
candidate below box=(126.6,2190.8,1001.3,2716.1) yc=2453.4 containment(r9_a in this)=0.000
candidate below box=(0.0,2219.2,107.8,2733.7)   yc=2476.4 containment(r9_a in this)=0.847
candidate below box=(122.6,2403.1,1011.4,2706.5) yc=2554.8 containment(r9_a in this)=0.000
candidate below box=(0.0,2431.6,104.1,2729.4)   yc=2580.5 containment(r9_a in this)=0.000
```
`r9_a` is 84.7% contained in the box at yc=2476.4 — a box belonging to a
**different, genuinely lower real row** (visually one row below the Yakult
row in the crop). This reconfirms Task 3's finding fresh: `r9_a` is a stray
duplicate/fragment of that lower row's item, not a real member of the Yakult
row.

**Critical check — does either algorithm actually bridge the Yakult row with
that different, lower real row?** Dumped the full row-by-row breakdown for
yc∈[1950,2750] under both OLD and NEW (`inv1_full_rows_1950_2750.py`,
run once per algorithm with the swap-verify procedure above) — the two
outputs are **identical**, row-for-row:
```
row (n=2) yc=(2192.5-2198.0)  -- fragment/top-portion duplicates of the 2 Yakult packs
row (n=3) yc=(2314.3-2343.1)  -- old row 9: r9_a + r9_b + r9_c
row (n=1) yc=(2366.8-2366.8)
row (n=4) yc=(2453.4-2476.4)  -- the "different, lower real row" (contains the box r9_a is 84.7% inside)
row (n=1) yc=(2525.8-2525.8)
row (n=1) yc=(2554.8-2554.8)
row (n=1) yc=(2580.5-2580.5)
```
The lower real row (yc 2453.4-2476.4, n=4) stays a **separate cluster_rows
group from old row 9 in both OLD and NEW** — `r9_a`'s stray fragment rides
along inside the Yakult row's own group in both algorithms, but this never
merges the Yakult row with the different row below in either algorithm.

### Investigation 1 conclusion

Old row 4 and old row 9 are **not evidence of the OLD algorithm bridging 2
real physical rows**, under the current n_2000 system:
- Row 4 is one genuine physical row (4 side-by-side bottles); kept as one row
  by both OLD and NEW, byte-identical membership.
- Row 9 is one genuine physical row (2 real Yakult packs) plus one stray
  duplicate-detection fragment (`r9_a`) that happens to ride along in the same
  cluster_rows group in both OLD and NEW — a `merge_adjacent_fragments`/dedup
  gap (separate, already-flagged, out-of-scope issue), not a case of either
  algorithm bridging the Yakult row with the real different row below it
  (confirmed identical row-grouping for both algorithms in that whole
  y-range).

---

## Investigation 2: Hảo Hảo case (test1.HEIC)

### Spot-check: are the 3 reference boxes still real current detections?

```
raw=60 merged=60 tol=18.9501 ygap=3.6483

box41_top_cup   vs raw:    best_match=(1109.0, 2840.4, 1326.8, 3116.4) IoU=0.9996
box45_both_cups vs raw:    best_match=(1116.5, 2843.7, 1326.5, 3254.9) IoU=0.9997
box48_bottom_cup vs raw:   best_match=(1125.5, 3098.8, 1318.6, 3359.2) IoU=0.9995

box41_top_cup   vs merged: IoU=0.9996 (same coords)
box45_both_cups vs merged: IoU=0.9997 (same coords)
box48_bottom_cup vs merged: IoU=0.9995 (same coords)
```
Confirmed: all 3 reference boxes from `tests/pipeline/test_box_filter.py` are
still real, near-exact (IoU≈0.9995-0.9997) raw and merged detections on the
current n_2000 checkpoint for test1.HEIC — `merge_adjacent_fragments` makes
no change to them.

### Does OLD `cluster_rows` bridge box45 with a different real row?

```
NEW algorithm: total rows=33
  box41 -> NEW row 22 (n=2): box41 + (1996.9,2883.3,2313.3,3107.9)
  box45 -> NEW row 24 (n=1): box45 alone
  box48 -> NEW row 26 (n=1): box48 alone
```
```
OLD algorithm: total rows=28
  box41 -> OLD row 19 (n=4): box41 + (1996.9,2883.3,2313.3,3107.9) +
                              (1657.7,2901.9,1980.0,3114.8) +
                              (1347.8,2864.2,1636.3,3157.7)
  box45 -> OLD row 20 (n=1): box45 alone
  box48 -> OLD row 22 (n=1): box48 alone
```
**`box45` is a singleton row (n=1) under BOTH algorithms.** It never joins
box41's row or box48's row-slot under the OLD single-linkage algorithm
either — the y-center gaps (box45 yc=3049.3 vs. OLD-row-19's last member
yc=3010.9, delta=38.4px; vs. box48 yc=3229.0, delta=179.7px) both exceed
`row_cluster_tolerance` (18.95px) directly, with no intermediate boxes to
chain through. The OLD algorithm's chaining failure mode (bridging via a
sequence of intermediate boxes each individually within tolerance) simply
doesn't apply here — there's a real, isolated gap that exceeds tolerance on
both sides of box45 (38.4px and 179.7px vs. 18.95px), not a chain of small
steps.

### Where box45 actually gets resolved: `filter_contained_boxes`

Ran the full `filter_anomalous_boxes` → `filter_contained_boxes` pipeline
(fresh, this session):
```
merged=60 anom=60 final=59 flagged=2
flagged boxes: (610.1, 2478.3, 820.7, 2808.7), (2341.1, 3130.3, 2652.4, 3486.5)
is box41 in boxes_final (kept)? True
is box45 in boxes_final (kept)? False
is box48 in boxes_final (kept)? True
is box45 in flagged? False
```
`box45` is silently dropped — `filter_contained_boxes` treats it as fully
redundant (its leftover area beyond `box41` is independently covered by
`box48`, meeting `LEFTOVER_COVERAGE_THRESHOLD=0.3`) — exactly the behavior
already asserted by
`tests/pipeline/test_box_filter.py::test_filter_contained_boxes_drops_haohao_crop45_when_both_children_present`
(`kept=={box41,box48}`, `flagged==[]`). `filter_anomalous_boxes` drops
*nothing* in either OLD or NEW mode for this image (`merged=60 → anom=60`
identically for both), so the 60 boxes reaching `filter_contained_boxes` are
identical regardless of which `cluster_rows` is used — this stage's outcome
is **entirely independent of the `cluster_rows` algorithm choice** for this
case.

### Full pipeline gap check (OLD vs NEW)

```
NEW: raw:60 merged:60 anom:60 final:59 (2 flagged) gaps:1
     gap: (1326.8, 2840.4, 1996.9, 3116.4)
OLD: raw:60 merged:60 anom:60 final:59 (2 flagged) gaps:0
```
Neither pipeline produces any gap or NEEDS-REVIEW flag anywhere near
box41/box45/box48 (x≈1109-1327). The one gap difference (NEW has 1, OLD has
0) is a **different** area entirely: NEW's gap at `(1326.8,2840.4,1996.9,
3116.4)` is caused by the NEW algorithm splitting OLD-row-19's 4
side-by-side noodle boxes (box41 + 3 others, x=1109-2313, verified
non-overlapping side-by-side x-ranges consistent with one real shelf row of
instant-noodle packets, visually confirmed in the annotated image) into 2
separate NEW rows (row 22: box41 + 1 box; the other 2 boxes land elsewhere) —
this is the same over-fragmentation failure mode already flagged for old
row 5/row 18 in the prior diagnostic, not a Hảo Hảo-specific effect.

Annotated images:
- `data/scan_viz/diagnostic_haohao_new/annotated.jpg` (current/NEW algorithm,
  full pipeline)
- `data/scan_viz/diagnostic_haohao_old/annotated.jpg` (OLD algorithm swapped
  in, full pipeline)

Visually the two are indistinguishable at the Hảo Hảo cups (bottom-left area
of the noodle/instant-food shelf, red/pink Hảo Hảo TomYum cups) — consistent
with the numeric finding that both algorithms treat this area identically.

### Investigation 2 conclusion

**This is not evidence of a `cluster_rows` chaining bug in the current
system.** `box45_both_cups` never bridges box41's row and box48's
"row"-slot under either algorithm — it's an isolated singleton row in both,
because the real y-center gaps around it exceed tolerance on both sides
(38.4px and 179.7px vs. 18.95px `row_cluster_tolerance`) and are too large
for the chaining mechanism to even apply, chain-of-intermediate-boxes or
not. The function that actually
resolves this case is `filter_contained_boxes` (containment/leftover-coverage
logic), which behaves identically regardless of which `cluster_rows`
version feeds it, and correctly drops `box45` as redundant given `box41` and
`box48` are both present. The evidence points squarely at
`filter_contained_boxes`, not `cluster_rows`, confirming the investigation's
suspected alternate hypothesis.

---

## Investigation 3: "Yakult test3 cũ" case

### Fresh values (not taken on faith)

`src/pipeline/scan.py` line 67: `ROW_CLUSTER_TOLERANCE_RATIO = 0.045065`.

Fresh `adaptive_tolerances()` call on test3.HEIC's real raw detections (same
run as Investigation 1's Step 1): `row_cluster_tolerance=23.4291`,
`y_gap_tolerance=4.5106` — confirms the ~23.4 value from Task 3/the
diagnostic, re-derived here independently.

### Real Yakult row + neighbors (already located in Investigation 1)

Yakult row (visually confirmed, yc≈2192.5-2343.1): fragment-duplicate pair at
yc 2192.5/2198.0 (n=2, span=5.5) + old-row-9's r9_b/r9_c (yc 2327.0/2343.1,
the 2 real full-height Yakult packs) + stray r9_a. Row below (different real
row, yc≈2453.4-2476.4, n=4).

### Does OLD algorithm, under n_2000 + current tolerance, chain the Yakult row into an erroneously large group spanning most of the row?

Full-pipeline OLD run (this session, swap-verified):
```
OLD: raw:54 merged:54 anom:50 final:47 (9 flagged) gaps:2
     gap: (1733.8, 1011.0, 2027.2, 1351.7)
     gap: (176.5, 1293.0, 1237.1, 1875.9)
check-region (127.4, 2005.7, 1882.1, 2680.6): clear (0 overlapping gap(s))
```
Full-pipeline NEW run (this session, current committed code):
```
NEW: raw:54 merged:54 anom:50 final:47 (9 flagged) gaps:3
     gap: (1733.8, 1011.0, 2027.2, 1351.7)
     gap: (176.5, 1293.0, 1237.1, 1875.9)
     gap: (306.0, 2933.9, 818.1, 3636.5)
check-region (127.4, 2005.7, 1882.1, 2680.6): clear (0 overlapping gap(s))
```
**No gap appears anywhere near the Yakult row's bounding region under either
algorithm.** The only row-grouping the OLD algorithm produces in this area
that exceeds tolerance is old row 9 (n=3, span=28.8, 1.23x tolerance) —
already characterized in Investigation 1 as 2 genuine Yakult items + 1 stray
duplicate fragment, not "nearly the entire row" merged into one erroneous
group. OLD's 2 gaps and NEW's 3 gaps are both accounted for by the
already-documented fermented-milk-bottle-row gaps (byte-identical
pre/post-fix, per the prior diagnostic) plus NEW's extra row-18
over-fragmentation gap — none are Yakult-row phantom gaps.

Annotated images:
- `data/scan_viz/diagnostic_yakult_old/annotated.jpg` (OLD algorithm, full
  pipeline)
- `data/scan_viz/diagnostic_yakult_new/annotated.jpg` (NEW/current algorithm,
  full pipeline)

Visual inspection (same full test3 crop as Investigation 1's row9 image,
which already shows this shelf clearly: 2 pink Yakult Hương Đào packs + 2
blue Yakult Light packs + 1 red Yakult pack on the right) shows a normal,
un-merged row of distinct Yakult multi-packs in both renders — no visible
sign of a giant erroneous merged box or a gap spanning the row.

### Investigation 3 conclusion

The original `full`-checkpoint-era claim ("`row_cluster_tolerance` >
~21.0-21.5px merges nearly an entire Yakult row into one group, producing a
gap spanning most of the row") **does not reproduce under the current n_2000
checkpoint + current tolerance (23.4291px)**. Under OLD algorithm + n_2000,
the Yakult area produces zero gaps and only a modest 1.23x-tolerance grouping
that's already explained by a real-genuine-row + 1 stray fragment, not a
large erroneous merge. This matches `scan.py`'s own recalibration comment
(historical note under `ROW_CLUSTER_TOLERANCE_RATIO`) that the `full`-era
danger zone (21.0-21.5px) doesn't reproduce with n_2000's box positions — this
investigation independently confirms that conclusion by directly running the
OLD `cluster_rows` algorithm against real n_2000 detections, rather than
inferring it from the tolerance-calibration sweep alone. This case was a
checkpoint-quality artifact of `full`, already fixed by the checkpoint
correction — unrelated to the `cluster_rows` algorithm.

---

## Investigation 4: Synthesis

Across all 4 originally-cited cases, re-verified under the current system
(n_2000 checkpoint + current recalibrated tolerances):

1. **Hảo Hảo (test1)** — Investigation 2: not a `cluster_rows` bug at all.
   `box45_both_cups` is an isolated singleton row under both OLD and NEW
   (real y-center gaps on both sides already exceed tolerance -- 38.4px and
   179.7px vs. 18.95px -- with no intermediate boxes to chain through). The
   case is fully resolved by
   `filter_contained_boxes`, identically regardless of `cluster_rows`
   version. **Ruled out.**
2. **Yakult, `full`-checkpoint-era (test3)** — Investigation 3: does not
   reproduce under n_2000. OLD algorithm produces zero gaps and no large
   erroneous merge anywhere near the Yakult row under the current checkpoint
   and tolerance. **Ruled out** (checkpoint artifact, already fixed
   separately; not a `cluster_rows` algorithm defect).
3. **"2 gap test3" case (h≈727-793px boxes, n_2000, post-recalibration)** —
   already refuted by Task 3: the boxes at the claimed "row boundary" are
   duplicate/fragment YOLO detections of the same bottles (96.8% containment),
   not a second physical row. Independently reconfirmed in this investigation
   for old row 4 specifically (Investigation 1: genuine single row, identical
   membership under OLD and NEW). **Ruled out.**
4. **Task 3's systematic sweep — old rows 4, 5, 9, 18:**
   - Old row 4: genuine single row, kept identically by both algorithms.
     **Not a bug; no difference between OLD and NEW.**
   - Old row 5: genuine single row (Task 3's visual confirmation), but the
     **NEW** algorithm over-fragments it into 2 pieces regardless of
     `max_span_multiplier` — evidence NEW is *worse* here, not that OLD was
     buggy.
   - Old row 9: genuine Yakult row (2 real items) + 1 stray duplicate
     fragment; re-verified fresh in Investigation 1 that neither algorithm
     ever merges the Yakult row with the different, genuinely lower real row
     — identical row-grouping under OLD and NEW in that entire y-range.
     **Not a bug; no difference between OLD and NEW.**
   - Old row 18: genuine single row (Task 3's visual confirmation), but the
     **NEW** algorithm over-fragments it into 3 pieces — same
     worse-not-better pattern as row 5.

Additionally, this investigation found a **fifth, fresh instance** of the
same over-fragmentation pattern while checking Investigation 2: NEW splits
OLD's row 19 (test1, 4 side-by-side instant-noodle boxes including box41,
visually one real shelf row) into 2 NEW rows, producing a phantom gap
`(1326.8,2840.4,1996.9,3116.4)` that OLD does not have (OLD: 0 gaps in that
image's noodle-shelf area; NEW: 1). This is unrelated to the Hảo Hảo
box41/45/48 claim itself but is more evidence in the same direction as row
5/18: the NEW algorithm's mean-check component fragments some genuine single
rows that the OLD algorithm correctly kept as one row.

### Verdict

**No case remains, under the current system, where the OLD single-linkage
algorithm demonstrably bridges 2 distinct real physical rows into one
erroneous group that the NEW algorithm fixes.** Every one of the 4
originally-cited cases either (a) doesn't reproduce as a `cluster_rows`
chaining bug at all under n_2000 + current tolerances (Hảo Hảo, Yakult
`full`-checkpoint, the h=727-793px "2 gap" case), or (b) is a genuine single
real row that OLD correctly keeps as one row and that NEW's row-mean check
incorrectly splits (old row 5, old row 18, plus the newly-found test1
noodle-shelf row 19 split) — i.e. evidence in the *opposite* direction, that
NEW is currently net-worse on the concrete real cases available in this
5-image calibration set. Old row 4 and old row 9 (this investigation's
targets) show **zero difference** between OLD and NEW — both algorithms treat
them identically, correctly, as genuine single rows.

**Reverting Task 1 (the `4a9ffed` `cluster_rows` change) is a defensible,
evidence-based conclusion** given everything checked here and in Task 3/the
prior diagnostic — this investigation does not revert anything itself; it
only lays out the evidence for the human's decision.

## What could not be verified

Nothing in this report is an estimate or a reused approximate number — every
box tuple, tolerance value, row index, containment ratio, and gap coordinate
above was produced by a real command in this session (or, where explicitly
marked, cross-checked byte-for-byte against Task 3's/the prior diagnostic's
already-established real numbers). There is no "could not verify" item to
flag for Investigations 1-4 as scoped by this task.
