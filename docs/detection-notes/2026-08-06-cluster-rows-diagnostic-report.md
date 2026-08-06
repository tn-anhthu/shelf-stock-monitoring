# Diagnostic Report: cluster_rows chaining fix — visual/mechanical evidence for human decision

Status: DONE_WITH_CONCERNS (see "What could not be verified" at the end — everything
else below is real command output, no estimates).

No tracked files were modified. `git status --porcelain` at the end of this
investigation shows only pre-existing untracked symlinks (`.venv-e2e`, `runs`,
`docs/superpowers`, `data/scan_viz/input/input_crop`) plus the new
`data/scan_viz/diagnostic_test{1,2,3}/annotated.jpg` outputs, all covered by
`.gitignore` (`data/scan_viz/*` with `!data/scan_viz/input/` /
`!data/scan_viz/review.xlsx` exceptions — confirmed via `git check-ignore -v`).
`scripts/verify_cluster_rows_fix.py` was used unmodified.

## Environment / methodology

- Weights: `runs/detect/runs/train_1a/n_2000/weights/best.pt`
- Python: `.venv-e2e/bin/python3` (symlink to main repo's venv, already present
  in this worktree at task start)
- Pipeline stages for Step 1 and Step 3: `detect_1a` → `adaptive_tolerances()`
  → `merge_adjacent_fragments()`. Step 1 then reproduces the OLD (pre-fix,
  single-linkage) `cluster_rows` verbatim from `git show
  4a9ffed~1:src/pipeline/row_clustering.py`. Step 3 calls the CURRENT
  (Task-1-fixed, committed) `cluster_rows(boxes_merged, row_cluster_tolerance)`
  at its default `max_span_multiplier=2.0`.
- Two throwaway scripts were written outside the tracked tree (not committed,
  not part of the repo):
  `/private/tmp/claude-501/-Users-realzoey-Project-shelf-stock-monitoring/7cd2c751-e4f5-4ff0-81c4-7a20c64b284a/scratchpad/step1_old_rows.py`
  and
  `/private/tmp/claude-501/-Users-realzoey-Project-shelf-stock-monitoring/7cd2c751-e4f5-4ff0-81c4-7a20c64b284a/scratchpad/step3_group_breakdown.py`.
- Step 4 annotated images were produced by the existing, unmodified
  `scripts/verify_cluster_rows_fix.py --out ...` (per-image `--check-region`
  flags for that image's regions).

---

## Step 1 result: exact real box coordinates for "old row 5" and "old row 18" (test3.HEIC)

Real run output (`raw: 54  merged: 54` — `merge_adjacent_fragments` made no
change to test3's box count, so old-row and current-row boxes below are
byte-identical to raw detections). `row_cluster_tolerance=23.4291`,
`y_gap_tolerance=4.5106`.

Reproducing the OLD (pre-fix) single-linkage `cluster_rows` on `boxes_merged`
produces 23 rows total; the 4 rows with span > tolerance (potential chaining
candidates) match Task 3's report exactly:

```
old row 4: n=4 yc=(1398.0-1424.6) span=26.6 (1.13x tolerance)
old row 5: n=5 yc=(1456.5-1500.3) span=43.9 (1.87x tolerance)
old row 9: n=3 yc=(2314.3-2343.1) span=28.8 (1.23x tolerance)
old row 18: n=12 yc=(3242.5-3338.5) span=96.0 (4.10x tolerance)
```

**Old row 5** (5 boxes, all real, byte-identical to raw detection output):

| box (x1,y1,x2,y2) | y-center | w | h |
|---|---|---|---|
| (185.9,1123.0,443.0,1877.7) | 1500.3 | 257.1 | 754.7 |
| (457.8,1119.3,704.8,1870.2) | 1494.8 | 247.0 | 751.0 |
| (722.5,1113.8,961.2,1848.9) | 1481.4 | 238.7 | 735.1 |
| (971.9,1104.1,1214.6,1831.2) | 1467.6 | 242.7 | 727.1 |
| (1234.4,1093.7,1472.4,1819.3) | 1456.5 | 238.0 | 725.6 |

Bounding region (min x1,y1 to max x2,y2 across all 5): **185.9,1093.7,1472.4,1877.7**

**Old row 18** (12 boxes, all real, byte-identical to raw detection output):

| box (x1,y1,x2,y2) | y-center | w | h |
|---|---|---|---|
| (0.0,3035.1,37.0,3641.7) | 3338.4 | 37.0 | 606.5 |
| (41.9,2933.9,306.0,3636.5) | 3285.2 | 264.1 | 702.7 |
| (330.6,3050.7,555.3,3626.3) | 3338.5 | 224.7 | 575.5 |
| (569.3,3045.5,798.5,3602.4) | 3324.0 | 229.2 | 556.9 |
| (818.1,3027.0,1053.4,3587.9) | 3307.4 | 235.2 | 561.0 |
| (1069.7,3021.0,1292.1,3575.9) | 3298.4 | 222.4 | 554.9 |
| (1305.3,3011.3,1522.5,3555.5) | 3283.4 | 217.2 | 544.3 |
| (1540.9,2999.0,1767.8,3538.5) | 3268.8 | 227.0 | 539.5 |
| (1784.8,2983.2,2009.1,3530.3) | 3256.7 | 224.3 | 547.1 |
| (2031.2,2995.7,2268.0,3523.0) | 3259.3 | 236.8 | 527.4 |
| (2293.3,2953.2,2514.4,3531.7) | 3242.5 | 221.1 | 578.5 |
| (2532.7,2946.1,2769.5,3552.9) | 3249.5 | 236.8 | 606.8 |

Bounding region (min x1,y1 to max x2,y2 across all 12): **0.0,2933.9,2769.5,3641.7**

These both match Task 3's previously-reported y-center ranges and x-range
lists exactly (old row 5: yc 1456.5-1500.3, x-ranges 186-443/458-705/722-961/
972-1215/1234-1472; old row 18: yc 3242.5-3338.5, n=12).

---

## Per-image results

For each region below: purpose, coordinates, annotated image path,
`scripts/verify_cluster_rows_fix.py`'s own `--check-region` PASS/overlap text
(from the unmodified script, run through the full pipeline including
`filter_anomalous_boxes` → `filter_contained_boxes` → `detect_gaps`), and the
Step 3 breakdown (current, Task-1-fixed `cluster_rows` at default
`max_span_multiplier=2.0`, run on `boxes_merged` only — no anomaly/containment
filtering — per the brief's Step 3 spec).

### test1.HEIC

Annotated image: `data/scan_viz/diagnostic_test1/annotated.jpg`
(`raw: 60  merged: 60  after filter_anomalous_boxes: 60  after
filter_contained_boxes: 59 (2 flagged)  gaps: 1`)

**Region: test1 new gap (post-fix)** — `1326.8,2840.4,1996.9,3116.4`

- Script's own check-region output: `check-region (1326.8, 2840.4, 1996.9,
  3116.4): PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. The single gap
  `detect_gaps` reports for this image is exactly `(1326.8, 2840.4, 1996.9,
  3116.4)`.
- Step 3 breakdown: `cluster_rows(boxes_merged, tolerance=18.9501)` →
  33 rows total. **2 distinct groups overlap this region** (row indices 22, 23):
  - Group row-22 (n=2, yc-span 2978.4-2995.6, delta=17.2): boxes
    `(1109.0,2840.4,1326.8,3116.4)` yc=2978.4, `(1996.9,2883.3,2313.3,3107.9)`
    yc=2995.6
  - Group row-23 (n=2, yc-span 3008.4-3010.9, delta=2.5): boxes
    `(1347.8,2864.2,1636.3,3157.7)` yc=3010.9, `(1657.7,2901.9,1980.0,3114.8)`
    yc=3008.4

### test2.HEIC

Annotated image: `data/scan_viz/diagnostic_test2/annotated.jpg`
(`raw: 95  merged: 95  after filter_anomalous_boxes: 94  after
filter_contained_boxes: 93 (8 flagged)  gaps: 13`)

`cluster_rows(boxes_merged, tolerance=15.5402)` → 27 rows total (Step 3, all
5 regions below).

**Region: test2 gap#1** — `1821.8,109.0,2422.4,646.9`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. Matching
  reported gap: `(1821.8, 109.0, 2422.4, 646.9)`.
- Step 3: **2 distinct groups overlap** (row indices 0, 1):
  - Group row-0 (n=7, yc-span 373.5-391.5, delta=18.0): boxes
    (0.0,143.6,187.3,614.5) yc=379.0; (1256.1,139.3,1438.8,638.0) yc=388.6;
    (1448.2,143.9,1632.7,639.0) yc=391.5; (1640.9,139.5,1821.8,643.1)
    yc=391.3; (2422.4,109.0,2611.0,646.9) yc=377.9; (2620.9,108.3,2820.7,638.6)
    yc=373.5; (2828.1,108.8,3022.2,646.1) yc=377.4
  - Group row-1 (n=3, yc-span 402.3-412.6, delta=10.3): boxes
    (1830.5,151.7,2020.9,673.5) yc=412.6; (2030.4,153.6,2212.8,653.6)
    yc=403.6; (2222.0,158.2,2412.2,646.5) yc=402.3

**Region: test2 gap#2** — `534.7,1796.9,2908.7,2142.8`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. Matching
  reported gap: `(534.7, 1796.9, 2908.7, 2142.8)`.
- Step 3: **3 distinct groups overlap** (row indices 12, 13, 14):
  - Group row-12 (n=4, yc-span 1963.2-1976.4, delta=13.2): boxes
    (32.5,1798.7,201.7,2134.1) yc=1966.4; (208.0,1804.8,368.9,2131.6)
    yc=1968.2; (379.0,1809.9,534.7,2142.8) yc=1976.4;
    (2908.7,1796.9,3023.7,2129.5) yc=1963.2
  - Group row-13 (n=9, yc-span 1987.1-2010.5, delta=23.4): boxes
    (540.3,1814.3,702.2,2170.9) yc=1992.6; (705.6,1817.2,870.2,2162.1)
    yc=1989.7; (883.7,1819.2,1045.1,2160.4) yc=1989.8;
    (1054.9,1813.5,1212.6,2160.7) yc=1987.1; (1221.6,1820.7,1374.4,2168.4)
    yc=1994.6; (1386.5,1833.6,1539.7,2168.2) yc=2000.9;
    (1551.5,1855.8,1711.2,2165.2) yc=2010.5; (1719.9,1839.0,1866.8,2162.3)
    yc=2000.7; (1875.1,1846.0,2025.5,2170.4) yc=2008.2
  - Group row-14 (n=5, yc-span 2014.0-2032.2, delta=18.2): boxes
    (2033.0,1855.2,2192.5,2172.7) yc=2014.0; (2199.7,1871.4,2366.9,2176.6)
    yc=2024.0; (2375.8,1873.5,2533.0,2185.0) yc=2029.2;
    (2540.9,1866.0,2689.1,2198.4) yc=2032.2; (2697.6,1855.6,2874.4,2208.6)
    yc=2032.1

**Region: test2 gap#3** — `2407.4,2370.0,2561.8,2713.1`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. Matching
  reported gap: `(2407.4, 2370.0, 2561.8, 2713.1)`.
- Step 3: **1 distinct group overlaps** (row index 17):
  - Group row-17 (n=1, yc-span 2552.7-2552.7, delta=0.0): box
    (2417.9,2391.5,2559.2,2714.0) yc=2552.7

**Region: test2 gap#4** — `898.3,2865.3,1763.9,3112.1`

- Script output: `PHANTOM GAP STILL PRESENT (6 overlapping gap(s))`. This
  region overlaps 6 of the 13 gaps `detect_gaps` reports for this image (the
  script does not print which — see the full 13-gap list logged for test2
  above/near the top of this section).
- Step 3: **7 distinct groups overlap** (row indices 19, 20, 21, 22, 24, 25, 26):
  - Group row-19 (n=1, yc-span 2965.3-2965.3, delta=0.0): box
    (909.1,2821.6,1102.9,3109.1) yc=2965.3
  - Group row-20 (n=2, yc-span 2985.7-2991.5, delta=5.8): boxes
    (698.6,2865.3,898.3,3106.1) yc=2985.7; (1763.9,2871.0,1974.6,3112.1)
    yc=2991.5
  - Group row-21 (n=2, yc-span 3006.1-3006.7, delta=0.7): boxes
    (482.6,2900.3,688.6,3113.2) yc=3006.7; (910.5,2904.6,1103.7,3107.5)
    yc=3006.1
  - Group row-22 (n=6, yc-span 3086.1-3107.2, delta=21.1): boxes
    (241.7,2890.9,482.3,3311.4) yc=3101.2; (494.2,2862.0,692.0,3310.2)
    yc=3086.1; (1122.7,2880.6,1321.1,3316.9) yc=3098.7;
    (1334.2,2881.1,1532.2,3332.2) yc=3106.6; (1754.7,2882.6,1962.1,3331.7)
    yc=3107.2; (2626.2,2858.3,2778.2,3340.5) yc=3099.4
  - Group row-24 (n=6, yc-span 3133.1-3144.9, delta=11.8): boxes
    (501.1,2977.9,703.3,3311.9) yc=3144.9; (1548.5,2953.4,1742.3,3331.8)
    yc=3142.6; (1973.5,2932.1,2179.5,3334.1) yc=3133.1;
    (2191.1,2935.2,2395.9,3339.0) yc=3137.1; (2403.5,2931.6,2611.4,3340.9)
    yc=3136.3; (2798.8,2921.9,3023.8,3359.8) yc=3140.8
  - Group row-25 (n=1, yc-span 3179.8-3179.8, delta=0.0): box
    (1125.6,3042.7,1320.5,3316.9) yc=3179.8
  - Group row-26 (n=6, yc-span 3202.1-3219.3, delta=17.2): boxes
    (506.2,3106.8,710.9,3306.3) yc=3206.6; (723.1,3121.1,910.7,3317.5)
    yc=3219.3; (923.0,3122.2,1116.4,3316.3) yc=3219.2;
    (1333.1,3077.5,1531.5,3326.7) yc=3202.1; (1547.6,3103.9,1740.4,3329.7)
    yc=3216.8; (1750.3,3085.0,1957.9,3331.4) yc=3208.2

**Region: test2 gap#5** — `688.6,2900.3,910.5,3113.2`

- Script output: `PHANTOM GAP STILL PRESENT (3 overlapping gap(s))`.
- Step 3: **6 distinct groups overlap** (row indices 19, 20, 21, 22, 24, 26) —
  same groups as gap#4's list minus row-25 (this region is a spatial subset
  near the same crowded area). Box lists for rows 19/20/21/22/24/26 are
  identical to those printed under gap#4 above (same underlying
  `cluster_rows` output, just a different check-region overlapping a subset
  of the same rows).

### test3.HEIC

Annotated image: `data/scan_viz/diagnostic_test3/annotated.jpg`
(`raw: 54  merged: 54  after filter_anomalous_boxes: 50  after
filter_contained_boxes: 47 (9 flagged)  gaps: 3`)

`cluster_rows(boxes_merged, tolerance=23.4291)` → 26 rows total (Step 3, all
4 regions below).

**Region: test3 known-gap#1 (byte-identical pre/post fix)** — `1733.8,1011.0,2027.2,1351.7`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. Matching
  reported gap: `(1733.8, 1011.0, 2027.2, 1351.7)`.
- Step 3: **4 distinct groups overlap** (row indices 1, 2, 4, 7):
  - Group row-1 (n=3, yc-span 1180.5-1200.2, delta=19.8): boxes
    (1475.1,1026.9,1733.8,1351.7) yc=1189.3; (2027.2,1011.0,2282.8,1349.9)
    yc=1180.5; (2297.4,1009.6,2553.9,1390.9) yc=1200.2
  - Group row-2 (n=1, yc-span 1274.6-1274.6, delta=0.0): box
    (1479.5,1027.0,1741.6,1522.2) yc=1274.6
  - Group row-4 (n=4, yc-span 1398.0-1424.6, delta=26.6): boxes
    (1482.3,1028.4,1742.9,1810.1) yc=1419.2; (1753.6,1011.9,2018.5,1804.8)
    yc=1408.3; (2032.8,1008.9,2285.4,1787.2) yc=1398.0;
    (2302.6,1081.2,2563.4,1768.0) yc=1424.6
  - Group row-7 (n=1, yc-span 1534.8-1534.8, delta=0.0): box
    (1764.2,1264.7,2027.2,1804.9) yc=1534.8

**Region: test3 known-gap#2 (byte-identical pre/post fix)** — `176.5,1293.0,1237.1,1875.9`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. Matching
  reported gap: `(176.5, 1293.0, 1237.1, 1875.9)`.
- Step 3: **3 distinct groups overlap** (row indices 5, 6, 8):
  - Group row-5 (n=3, yc-span 1456.5-1481.4, delta=24.9): boxes
    (722.5,1113.8,961.2,1848.9) yc=1481.4; (971.9,1104.1,1214.6,1831.2)
    yc=1467.6; (1234.4,1093.7,1472.4,1819.3) yc=1456.5
  - Group row-6 (n=2, yc-span 1494.8-1500.3, delta=5.6): boxes
    (185.9,1123.0,443.0,1877.7) yc=1500.3; (457.8,1119.3,704.8,1870.2)
    yc=1494.8
  - Group row-8 (n=3, yc-span 1578.0-1597.5, delta=19.6): boxes
    (0.0,1293.0,176.5,1875.9) yc=1584.4; (1237.1,1372.9,1468.6,1822.2)
    yc=1597.5; (2912.7,1368.2,3024.0,1787.7) yc=1578.0

**Region: test3 old-row-5 bounding region (derived, Step 1)** — `185.9,1093.7,1472.4,1877.7`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))` — this
  bounding region spatially overlaps known-gap#2's coordinates (they share
  most of the same x/y area), so it picks up the same reported gap
  `(176.5, 1293.0, 1237.1, 1875.9)`.
- Step 3: **3 distinct groups overlap** — **identical group set to
  known-gap#2 above** (row indices 5, 6, 8; same box lists as printed there).
  Cross-checking against the exact 5-box old-row-5 list from Step 1:
  - Group row-5's 3 boxes (722.5,1113.8,961.2,1848.9),
    (971.9,1104.1,1214.6,1831.2), (1234.4,1093.7,1472.4,1819.3) are
    byte-identical to 3 of the 5 original old-row-5 boxes.
  - Group row-6's 2 boxes (185.9,1123.0,443.0,1877.7),
    (457.8,1119.3,704.8,1870.2) are byte-identical to the other 2 of the 5
    original old-row-5 boxes.
  - **Together, groups row-5 and row-6 account for all 5 original old-row-5
    boxes, split 3+2.**
  - Group row-8's 3 boxes — (0.0,1293.0,176.5,1875.9),
    (1237.1,1372.9,1468.6,1822.2), (2912.7,1368.2,3024.0,1787.7) — do **not**
    match any of the 5 original old-row-5 boxes exactly. Group row-8 only
    appears in this region's match list because one of its boxes,
    (1237.1,1372.9,1468.6,1822.2), geometrically overlaps the bounding
    rectangle (its x-range 1237.1-1468.6 is close to, but not identical to,
    original old-row-5 box E's x-range 1234.4-1472.4; its y-range 1372.9-1822.2
    differs from E's 1093.7-1819.3). This is a geometric-overlap artifact of
    using a bounding-rectangle region, not evidence that row-8 is part of
    old-row-5.

**Region: test3 old-row-18 bounding region (derived, Step 1)** — `0.0,2933.9,2769.5,3641.7`

- Script output: `PHANTOM GAP STILL PRESENT (1 overlapping gap(s))`. Matching
  reported gap: `(306.0, 2933.9, 818.1, 3636.5)`.
- Step 3: **6 distinct groups overlap** (row indices 16, 17, 19, 20, 21, 22):
  - Group row-16 (n=1, yc-span 3084.8-3084.8, delta=0.0): box
    (44.1,2936.8,302.8,3232.8) yc=3084.8
  - Group row-17 (n=1, yc-span 3175.9-3175.9, delta=0.0): box
    (1778.9,2991.6,2010.1,3360.2) yc=3175.9
  - Group row-19 (n=5, yc-span 3242.5-3268.8, delta=26.3): boxes
    (1540.9,2999.0,1767.8,3538.5) yc=3268.8; (1784.8,2983.2,2009.1,3530.3)
    yc=3256.7; (2031.2,2995.7,2268.0,3523.0) yc=3259.3;
    (2293.3,2953.2,2514.4,3531.7) yc=3242.5; (2532.7,2946.1,2769.5,3552.9)
    yc=3249.5
  - Group row-20 (n=4, yc-span 3283.4-3307.4, delta=24.0): boxes
    (41.9,2933.9,306.0,3636.5) yc=3285.2; (818.1,3027.0,1053.4,3587.9)
    yc=3307.4; (1069.7,3021.0,1292.1,3575.9) yc=3298.4;
    (1305.3,3011.3,1522.5,3555.5) yc=3283.4
  - Group row-21 (n=3, yc-span 3324.0-3338.5, delta=14.5): boxes
    (0.0,3035.1,37.0,3641.7) yc=3338.4; (330.6,3050.7,555.3,3626.3)
    yc=3338.5; (569.3,3045.5,798.5,3602.4) yc=3324.0
  - Group row-22 (n=1, yc-span 3385.5-3385.5, delta=0.0): box
    (52.6,3141.5,316.2,3629.6) yc=3385.5
  - Cross-checking against the exact 12-box old-row-18 list from Step 1:
    **groups row-19 (5 boxes), row-20 (4 boxes), and row-21 (3 boxes) are, in
    total, byte-identical to all 12 original old-row-18 boxes**, split 5+4+3.
    Groups row-16, row-17, and row-22 (1 box each) do **not** match any of
    the 12 original old-row-18 boxes exactly — each has an x-range close to
    one of the 12 originals but a different y-range (e.g. row-16's box
    (44.1,2936.8,302.8,3232.8) has x-range close to original box #2
    (41.9,2933.9,306.0,3636.5) but y2=3232.8 vs. 3636.5). These 3 groups only
    appear in this region's match list as a geometric-overlap artifact of the
    bounding rectangle, not as evidence they are part of old-row-18.

---

## What could not be verified / concerns

- The bounding-region method for old-row-5 and old-row-18 (min/max over the
  member boxes) is, by construction, a large rectangle that can geometrically
  overlap boxes that are not members of the original row (documented above
  for group row-8 in old-row-5's region, and groups row-16/17/22 in
  old-row-18's region). This is a mechanical property of the region-overlap
  check reused from `scripts/verify_cluster_rows_fix.py`'s `box_overlaps_region`,
  not a defect in `cluster_rows` — flagged so the human reviewer doesn't
  mistake "N groups overlap the region" for "N groups made up entirely of the
  original row's boxes." The byte-identical cross-check for each region
  (given above) separates the two.
- test2 gap#4 and gap#5's script output reports "6 overlapping gap(s)" and "3
  overlapping gap(s)" respectively but does not print *which* of the 13 total
  gaps overlap by coordinate (the script's `--check-region` output only gives
  a count) — the full list of all 13 gaps for test2 is logged above/verbatim
  from the script's own stdout, but I did not independently re-derive which
  named gap indices correspond to which check-region beyond what's mechanically
  implied by the coordinates.
- I did not re-verify test1/test2's 6 given gap coordinates via independent
  re-computation (per the task's instruction, these were usable as-given from
  Task 2/3's reports) — I only ran them through the current script and Step-3
  breakdown, which is what this diagnostic asked for.
- No numbers in this report are estimated; every box/gap/group value above is
  copied verbatim from real command output.
