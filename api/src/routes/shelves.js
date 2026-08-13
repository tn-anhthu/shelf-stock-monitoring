const express = require('express');
const { CATEGORIES } = require('../config/shelfRegistry');

const router = express.Router();

router.get('/shelves', (req, res) => {
  res.status(200).json({ categories: CATEGORIES });
});

module.exports = router;
