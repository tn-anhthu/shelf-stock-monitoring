"""Diagnose why detect_gaps() did or didn't flag an expected gap on a real shelf
photo. Only runs YOLO (no SigLIP2 load needed), then prints every intermediate
step of the gap-detection heuristic so a missed/false gap can be root-caused
instead of guessed at:

  - every raw box YOLO detected (sorted by y-center)
  - how those boxes got clustered into rows (row_cluster_tolerance)
  - per row: sorted boxes, avg width, and every adjacent gap_width vs the
    width_multiplier * avg_width threshold that decides if it's flagged

Usage:
    python3 scripts/debug_gap_detection.py --image path/to/shelf.jpg \
        --weights sku110k_yolo26n_results/weights/best.pt \
        --row-tolerance 20.0 --width-multiplier 1.5
"""
import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.row_clustering import box_y_center as _y_center
from src.pipeline.row_clustering import cluster_rows as _cluster_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--row-tolerance", type=float, default=20.0)
    parser.add_argument("--width-multiplier", type=float, default=1.5)
    args = parser.parse_args()

    yolo_model = load_model_1a(Path(args.weights))
    shelf_image = Image.open(args.image)

    boxes = detect_1a(yolo_model, shelf_image)
    print(f"YOLO detected {len(boxes)} boxes total\n")

    print("All boxes, sorted by y-center (x1, y1, x2, y2) | y_center | width:")
    for box in sorted(boxes, key=_y_center):
        x1, y1, x2, y2 = box
        print(f"  ({x1:6.1f}, {y1:6.1f}, {x2:6.1f}, {y2:6.1f})  y_center={_y_center(box):6.1f}  width={x2-x1:6.1f}")

    if len(boxes) < 2:
        print("\nFewer than 2 boxes total — detect_gaps() always returns [] in this case.")
        return

    global_median_width = statistics.median(box[2] - box[0] for box in boxes)
    print(f"\nGlobal median width (fallback for rows with <2 boxes): {global_median_width:.1f}")

    rows = _cluster_rows(boxes, args.row_tolerance)
    print(f"\nRow clustering (tolerance={args.row_tolerance}) produced {len(rows)} row(s):")

    for row_idx, row in enumerate(rows):
        row_sorted = sorted(row, key=lambda b: b[0])
        y_centers = [f"{_y_center(b):.1f}" for b in row_sorted]
        print(f"\n  Row {row_idx}: {len(row_sorted)} box(es), y_centers=[{', '.join(y_centers)}]")

        if len(row_sorted) < 2:
            print(f"    -> only {len(row_sorted)} box in this row: gap comparison SKIPPED entirely for it "
                  f"(this is the 'continue' branch in gap_detection.py — a real gap next to a lone box "
                  f"in its own row-cluster will NEVER be flagged, regardless of width_multiplier)")
            continue

        avg_width = sum(b[2] - b[0] for b in row_sorted) / len(row_sorted)
        threshold = args.width_multiplier * avg_width
        print(f"    avg_width={avg_width:.1f}  threshold (width_multiplier x avg_width)={threshold:.1f}")

        for i in range(len(row_sorted) - 1):
            current, nxt = row_sorted[i], row_sorted[i + 1]
            gap_width = nxt[0] - current[2]
            flagged = gap_width > threshold
            marker = " <-- FLAGGED" if flagged else ""
            print(f"    gap between box {i} and {i+1}: gap_width={gap_width:6.1f}  "
                  f"({'>' if flagged else '<='} threshold){marker}")

    gaps = detect_gaps(boxes, row_cluster_tolerance=args.row_tolerance, width_multiplier=args.width_multiplier)
    print(f"\nFinal detect_gaps() result: {len(gaps)} gap(s)")
    for g in gaps:
        print(f"  {tuple(round(v) for v in g)}")


if __name__ == "__main__":
    main()
