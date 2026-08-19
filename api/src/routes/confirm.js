const express = require('express');
const { scansDb } = require('../services/scansDb');
const { isActiveShelf } = require('../config/shelfRegistry');

const router = express.Router();

router.post('/confirm', (req, res) => {
  const {
    scan_id: scanId,
    category,
    container,
    quantities,
    total_value: totalValue,
    boxes,
  } = req.body;

  if (!scanId || !category || !container || !Array.isArray(quantities) || quantities.length === 0) {
    return res.status(400).json({
      error: 'scan_id, category, container, and a non-empty quantities array are required',
    });
  }

  if (!isActiveShelf(category, container)) {
    return res.status(400).json({ error: 'category/container is missing or not active' });
  }

  const quantitiesWithSource = quantities.map((q) => ({ ...q, source: q.source ?? 'scan' }));

  scansDb.insertScan({
    scanId,
    category,
    container,
    quantities: quantitiesWithSource,
    totalValue: totalValue ?? 0,
    boxes,
  });

  return res.status(200).json({ confirmed: true, scan_id: scanId });
});

module.exports = router;
