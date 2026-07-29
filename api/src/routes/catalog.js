const express = require('express');
const { catalog } = require('../services/catalog');

const router = express.Router();

router.get('/catalog', (req, res) => {
  const items = Array.from(catalog.entries()).map(([skuId, entry]) => ({
    sku_id: skuId,
    name: entry.name.normalize('NFC'),
    price: entry.price,
    shelf_full_qty: entry.shelfFullQty,
  }));
  res.status(200).json(items);
});

module.exports = router;
