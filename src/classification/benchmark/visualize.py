"""Save a handful of test crops with their true vs predicted category names, for
manual sanity-checking. Usage: python3 -m src.classification.benchmark.visualize --n 5
"""
import argparse
from functools import partial
from pathlib import Path

from src.classification.benchmark.catalog import build_catalog
from src.classification.benchmark.data import build_catalog_source, load_category_names, load_test_crops
from src.classification.benchmark.embed_clip import embed_image_clip, load_model_clip
from src.classification.benchmark.retrieve import rank_categories

OUTPUT_DIR = Path("data/classification_results/sample_crops")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()

    test_crops = load_test_crops(n_images=3)[: args.n]
    needed_categories = {c["category"] for c in test_crops}
    catalog_source = build_catalog_source(needed_categories, max_per_category=3)
    names = load_category_names()

    model, processor = load_model_clip()
    embed_fn = partial(embed_image_clip, model, processor)
    catalog = build_catalog(catalog_source, embed_fn)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, crop in enumerate(test_crops):
        crop["image"].save(OUTPUT_DIR / f"crop_{i}.png")
        ranking = rank_categories(embed_fn(crop["image"]), catalog)[:3]
        true_name = names[crop["category"]]
        pred_names = [names[c] for c in ranking]
        (OUTPUT_DIR / f"crop_{i}.txt").write_text(
            f"true category: {true_name}\ntop-3 predicted (CLIP): {pred_names}\n"
        )

    print(f"Saved {len(test_crops)} crops + predictions to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
