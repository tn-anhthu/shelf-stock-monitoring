"""Diagnostic: measure shelf-rail tilt in the 14 raw test6-19 photos to check
the hypothesis "off-axis camera angle causes phantom/missed gaps".

Read-only. Does not import or touch anything in src/pipeline/ -- this only
looks at the raw HEIC pixels with OpenCV line detection, independent of the
detection/gap pipeline.

Method, per image:
  1. Load HEIC via pillow_heif, apply EXIF orientation, downscale, grayscale.
  2. Canny edge detection + HoughLinesP to find long straight line segments.
  3. Keep segments within +/-20 deg of horizontal (candidate shelf rails /
     price-tag strip edges / shelf-lip edges).
  4. Take the longest N% of those (long lines are more likely to be a real
     structural edge than noise/text), and report:
       - mean_angle_deg / std_angle_deg: tilt vs true horizontal
       - mean_abs_angle_deg: tilt magnitude, sign-independent
       - keystone_ratio: mean length of top-half-of-frame lines vs
         bottom-half-of-frame lines. Ratio far from 1.0 suggests the camera
         wasn't shooting perpendicular to the shelf face (tilted up/down).

Usage:
    python3 scripts/measure_shelf_tilt.py
    python3 scripts/measure_shelf_tilt.py --out-csv data/scan_viz/shelf_tilt_diagnostic.csv
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pillow_heif

pillow_heif.register_heif_opener()
from PIL import Image, ImageOps

INPUT_DIR = Path("data/scan_viz/input")

# Grouping per Thu's request. test18 is deliberately excluded from
# CONFIRMED_ERROR: known root cause there is crop-noise from the cabinet
# border, not camera angle.
CONFIRMED_ERROR = ["test14", "test15", "test16"]
CONFIRMED_CLEAN = ["test13", "test19", "test17"]
DISPUTED = ["test6", "test7", "test8", "test9", "test10", "test11", "test12"]

RESIZE_WIDTH = 1600  # downscale long side so Hough params behave consistently across shots
ANGLE_RANGE_DEG = 20.0  # candidate horizontal lines: within +/-20 deg of true horizontal
TOP_LENGTH_FRACTION = 0.15  # use the longest 15% of candidate lines for the angle estimate


def load_gray(path: Path) -> np.ndarray:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # normalize orientation before measuring angles
    img = img.convert("L")
    w, h = img.size
    if w > RESIZE_WIDTH:
        scale = RESIZE_WIDTH / w
        img = img.resize((RESIZE_WIDTH, round(h * scale)), Image.LANCZOS)
    return np.array(img)


def find_horizontal_lines(gray: np.ndarray) -> list[dict]:
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    min_len = max(30, int(w * 0.08))
    raw_lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=60,
        minLineLength=min_len, maxLineGap=15,
    )
    if raw_lines is None:
        return []
    raw_lines = raw_lines.reshape(-1, 4)  # cv2 build-dependent: (N,4) or (N,1,4)

    lines = []
    for x1, y1, x2, y2 in raw_lines:
        dx, dy = float(x2 - x1), float(y2 - y1)
        length = float(np.hypot(dx, dy))
        if length == 0:
            continue
        angle = float(np.degrees(np.arctan2(dy, dx)))
        if angle <= -90:
            angle += 180
        elif angle > 90:
            angle -= 180
        if abs(angle) > ANGLE_RANGE_DEG:
            continue
        lines.append({"angle": angle, "length": length, "mid_y": (y1 + y2) / 2.0})
    return lines


def summarize(lines: list[dict], image_height: int) -> dict | None:
    if not lines:
        return None
    lines_by_length = sorted(lines, key=lambda l: l["length"], reverse=True)
    n_top = max(1, round(len(lines_by_length) * TOP_LENGTH_FRACTION))
    top = lines_by_length[:n_top]

    angles = np.array([l["angle"] for l in top])
    mean_angle = float(np.mean(angles))
    std_angle = float(np.std(angles))
    mean_abs_angle = float(np.mean(np.abs(angles)))

    mid_y = image_height / 2.0
    top_half_lens = [l["length"] for l in top if l["mid_y"] < mid_y]
    bottom_half_lens = [l["length"] for l in top if l["mid_y"] >= mid_y]
    keystone_ratio = None
    if top_half_lens and bottom_half_lens:
        keystone_ratio = float(np.mean(top_half_lens) / np.mean(bottom_half_lens))

    return {
        "n_lines_total": len(lines),
        "n_lines_used": n_top,
        "mean_angle_deg": mean_angle,
        "std_angle_deg": std_angle,
        "mean_abs_angle_deg": mean_abs_angle,
        "keystone_ratio": keystone_ratio,
    }


def fmt(v, nd=2):
    return f"{v:.{nd}f}" if v is not None else "n/a"


def print_table(rows: dict[str, dict | None]) -> None:
    header = f"{'image':<10} {'n_lines':>7} {'mean_angle':>11} {'std_angle':>10} {'mean_abs':>9} {'keystone':>9}"
    print(header)
    print("-" * len(header))
    for name, s in rows.items():
        if s is None:
            print(f"{name:<10} {'no horizontal lines found':>50}")
            continue
        print(
            f"{name:<10} {s['n_lines_used']:>7} {fmt(s['mean_angle_deg']):>11} "
            f"{fmt(s['std_angle_deg']):>10} {fmt(s['mean_abs_angle_deg']):>9} "
            f"{fmt(s['keystone_ratio']):>9}"
        )


def group_stats(rows: dict[str, dict | None], names: list[str]) -> dict:
    vals_abs_angle = [rows[n]["mean_abs_angle_deg"] for n in names if rows.get(n)]
    vals_std = [rows[n]["std_angle_deg"] for n in names if rows.get(n)]
    vals_keystone_dev = [
        abs(rows[n]["keystone_ratio"] - 1.0)
        for n in names
        if rows.get(n) and rows[n]["keystone_ratio"] is not None
    ]
    return {
        "n": len(vals_abs_angle),
        "mean_abs_angle": float(np.mean(vals_abs_angle)) if vals_abs_angle else None,
        "mean_std_angle": float(np.mean(vals_std)) if vals_std else None,
        "mean_keystone_dev": float(np.mean(vals_keystone_dev)) if vals_keystone_dev else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-csv", type=str, default=None, help="optional path to also write the table as CSV")
    args = parser.parse_args()

    all_names = CONFIRMED_ERROR + CONFIRMED_CLEAN + DISPUTED
    results: dict[str, dict | None] = {}

    for name in all_names:
        path = INPUT_DIR / f"{name}.HEIC"
        if not path.exists():
            print(f"[skip] {path} not found")
            results[name] = None
            continue
        gray = load_gray(path)
        lines = find_horizontal_lines(gray)
        results[name] = summarize(lines, gray.shape[0])

    print("\n=== All 14 images ===")
    print_table(results)

    low_sample = [n for n, s in results.items() if s and s["n_lines_used"] < 5]
    if low_sample:
        print(f"\n[caveat] low line count (<5 used), angle estimate less reliable for: {', '.join(low_sample)}")

    if args.out_csv:
        out_path = Path(args.out_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as f:
            f.write("image,n_lines_used,mean_angle_deg,std_angle_deg,mean_abs_angle_deg,keystone_ratio\n")
            for name, s in results.items():
                if s is None:
                    f.write(f"{name},,,,,\n")
                else:
                    keystone_str = "" if s["keystone_ratio"] is None else f"{s['keystone_ratio']:.4f}"
                    f.write(
                        f"{name},{s['n_lines_used']},{s['mean_angle_deg']:.4f},"
                        f"{s['std_angle_deg']:.4f},{s['mean_abs_angle_deg']:.4f},"
                        f"{keystone_str}\n"
                    )
        print(f"\nCSV written to {out_path}")

    print("\n=== Confirmed error group (test14, test15, test16) vs confirmed clean group (test13, test19, test17) ===")
    err = group_stats(results, CONFIRMED_ERROR)
    clean = group_stats(results, CONFIRMED_CLEAN)
    print(f"error group  (n={err['n']}): mean|angle|={fmt(err['mean_abs_angle'])} deg, "
          f"mean std_angle={fmt(err['mean_std_angle'])} deg, mean |keystone-1|={fmt(err['mean_keystone_dev'], 3)}")
    print(f"clean group  (n={clean['n']}): mean|angle|={fmt(clean['mean_abs_angle'])} deg, "
          f"mean std_angle={fmt(clean['mean_std_angle'])} deg, mean |keystone-1|={fmt(clean['mean_keystone_dev'], 3)}")

    if err["mean_abs_angle"] is not None and clean["mean_abs_angle"] is not None:
        diff_angle = err["mean_abs_angle"] - clean["mean_abs_angle"]
        print(f"\nangle diff (error - clean): {fmt(diff_angle)} deg")
    if err["mean_keystone_dev"] is not None and clean["mean_keystone_dev"] is not None:
        diff_keystone = err["mean_keystone_dev"] - clean["mean_keystone_dev"]
        print(f"keystone-deviation diff (error - clean): {fmt(diff_keystone, 3)}")

    print(
        "\nNote: n=3 vs n=3 -- these numbers are directional signal only, not a "
        "statistically reliable conclusion. Not drawing a recommendation here; "
        "reported for Thu to decide next step."
    )

    print("\n=== Disputed group (reported separately, not compared) ===")
    print_table({n: results[n] for n in DISPUTED})


if __name__ == "__main__":
    main()
