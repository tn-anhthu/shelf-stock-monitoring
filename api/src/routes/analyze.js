const express = require('express');
const multer = require('multer');
const mlService = require('../services/mlService');
const { catalog } = require('../services/catalog');
const { isActiveShelf } = require('../config/shelfRegistry');
const { buildSuccessResult, buildFailedResult } = require('../services/analyzeResult');

const upload = multer({ storage: multer.memoryStorage() });
const router = express.Router();

router.post('/analyze', upload.single('image'), async (req, res) => {
  const { category, container } = req.body;

  if (!category || !container || !req.file) {
    return res.status(400).json({
      error: 'category, container, and image are all required',
    });
  }

  if (!isActiveShelf(category, container)) {
    return res.status(400).json({ error: 'category/container is missing or not active' });
  }

  let mlResult;
  try {
    mlResult = await mlService.predict(req.file.buffer, req.file.originalname, req.file.mimetype);
  } catch (err) {
    return res.status(200).json(
      buildFailedResult({ category, container, errorMessage: err.message })
    );
  }

  return res
    .status(200)
    .json(buildSuccessResult({ category, container, mlResult, catalog }));
});

module.exports = router;
