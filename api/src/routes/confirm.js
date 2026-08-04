const express = require('express');
const { scansDb } = require('../services/scansDb');

const router = express.Router();

router.post('/confirm', (req, res) => {
  const {
    scan_id: scanId,
    store_id: storeId,
    shelf_id: shelfId,
    quantities,
    total_value: totalValue,
  } = req.body;

  if (!scanId || !storeId || !shelfId || !Array.isArray(quantities) || quantities.length === 0) {
    return res.status(400).json({
      error: 'scan_id, store_id, shelf_id, and a non-empty quantities array are required',
    });
  }

  scansDb.insertScan({ scanId, storeId, shelfId, quantities, totalValue: totalValue ?? 0 });

  return res.status(200).json({ confirmed: true, scan_id: scanId });
});

module.exports = router;
