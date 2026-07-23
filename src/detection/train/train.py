"""Train YOLOv8 nano on a materialized SKU-110K subset.

Usage: python3 -m src.detection.train.train --n-train 400 --n-val 50 --epochs 8 --name pilot
"""
import argparse
import time
from pathlib import Path

from ultralytics import YOLO

from src.detection.train.data import materialize_yolo_dataset

DATA_DIR = Path("data/yolo_train")
RUNS_DIR = Path("runs/train_1a")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-train", type=int, default=400)
    parser.add_argument("--n-val", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="mps")
    parser.add_argument("--name", type=str, default="pilot")
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    parser.add_argument("--close-mosaic", type=int, default=10,
                         help="Disable mosaic augmentation for the last N epochs (ultralytics "
                              "default: 10). If N >= --epochs, mosaic is disabled almost the "
                              "entire run — pass a smaller value for short runs.")
    args = parser.parse_args()

    print(f"Materializing {args.n_train} train / {args.n_val} val images...")
    data_yaml = materialize_yolo_dataset(args.n_train, args.n_val, DATA_DIR)

    model = YOLO(args.model)
    start = time.time()
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        device=args.device,
        project=str(RUNS_DIR),
        name=args.name,
        close_mosaic=args.close_mosaic,
    )
    elapsed = time.time() - start
    per_epoch = elapsed / args.epochs
    print(f"\nTraining finished in {elapsed:.1f}s ({per_epoch:.1f}s/epoch, "
          f"{per_epoch / args.n_train:.4f}s/epoch/image)")
    best_path = RUNS_DIR / args.name / "weights" / "best.pt"
    print(f"Best weights: {best_path}")


if __name__ == "__main__":
    main()
