// Neighbor-inference suggestion algorithm -- spec:
// docs/superpowers/specs/2026-08-19-missing-items-neighbor-inference-design.md §4.1a/§5
//
// clusterRows mirrors src/pipeline/row_clustering.py::cluster_rows (same
// y-center single-linkage clustering, same default 20px tolerance already
// tuned and live in gap_detection.py) -- reimplemented here rather than
// imported because this runs in the Node API layer over already-detected,
// already-persisted boxes at dashboard-fetch time, not by re-invoking the
// Python ml-service pipeline. Known caveat inherited from the original:
// single-linkage chaining could in theory merge two physically distinct
// rows -- documented as inert-in-practice in
// docs/detection-notes/2026-08-06-cluster-rows-old-algorithm-reverification.md.
// Here the effect (if it ever occurs) is under-recall of neighbor
// candidates, not a wrong suggestion -- consistent with "abstain over guess"
// (spec §5.2).

function productLineKey(skuId) {
  return skuId.split('_')[0];
}

function boxYCenter(box) {
  return (box.bbox[1] + box.bbox[3]) / 2;
}

function clusterRows(boxes, tolerance = 20) {
  const sorted = [...boxes].sort((a, b) => boxYCenter(a) - boxYCenter(b));
  const rows = [];
  for (const box of sorted) {
    const lastRow = rows[rows.length - 1];
    if (lastRow && boxYCenter(box) - boxYCenter(lastRow[lastRow.length - 1]) <= tolerance) {
      lastRow.push(box);
    } else {
      rows.push([box]);
    }
  }
  return rows;
}

function toDisplay(skuId, catalog) {
  return { sku_id: skuId, sku_name: catalog.get(skuId)?.name ?? skuId };
}

function findMissingItemSuggestions(scanRow, catalog) {
  const boxes = scanRow.boxes ?? [];
  const confirmedGaps = boxes.filter((b) => b.type === 'gap' && !b.needs_review);
  if (confirmedGaps.length === 0) return [];

  const detectedProducts = boxes.filter(
    (b) => b.type === 'product' && b.sku_id && !b.is_unknown && !b.excluded_from_count,
  );
  const detectedSkuIds = new Set(detectedProducts.map((p) => p.sku_id));
  const rows = clusterRows([...confirmedGaps, ...detectedProducts]);

  return confirmedGaps.map((gap) => {
    const row = rows.find((r) => r.includes(gap));
    const neighborProducts = row.filter((b) => b.type === 'product');
    const neighborSkuIds = [...new Set(neighborProducts.map((p) => p.sku_id))];
    const neighborLineKeys = new Set(neighborSkuIds.map(productLineKey));

    const candidateIds = new Set();
    for (const [skuId] of catalog) {
      if (neighborLineKeys.has(productLineKey(skuId)) && !detectedSkuIds.has(skuId)) {
        candidateIds.add(skuId);
      }
    }

    return {
      gap_box_id: gap.box_id,
      bbox: gap.bbox,
      nearby_skus: neighborSkuIds.map((id) => toDisplay(id, catalog)),
      candidates: [...candidateIds].slice(0, 3).map((id) => toDisplay(id, catalog)),
    };
  });
}

module.exports = { productLineKey, clusterRows, findMissingItemSuggestions };
