const express = require('express');
const { isActiveShelf } = require('../config/shelfRegistry');
const { scansDb } = require('../services/scansDb');
const { buildDashboardPayload } = require('../services/dashboard');

const router = express.Router();

router.get('/dashboard', (req, res) => {
  const { category, container } = req.query;

  if (!category || !container || !isActiveShelf(category, container)) {
    return res.status(400).json({ error: 'category/container is missing or not active' });
  }

  const scanRow = scansDb.getLatestScan(category, container);
  return res.status(200).json(buildDashboardPayload(scanRow));
});

module.exports = router;
