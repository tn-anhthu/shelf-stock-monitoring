const express = require('express');
const multer = require('multer');
const mlService = require('../services/mlService');
const { catalog } = require('../services/catalog');
const { buildSuccessResult, buildFailedResult } = require('../services/analyzeResult');

const upload = multer({ storage: multer.memoryStorage() });
const router = express.Router();

router.post('/analyze', upload.single('image'), async (req, res) => {
  const { store_id: storeId, shelf_id: shelfId } = req.body;

  if (!storeId || !shelfId || !req.file) {
    return res.status(400).json({
      error: 'store_id, shelf_id, and image are all required',
    });
  }

  let mlResult;
  try {
    mlResult = await mlService.predict(req.file.buffer, req.file.originalname, req.file.mimetype);
  } catch (err) {
    return res.status(200).json(
      buildFailedResult({ storeId, shelfId, errorMessage: err.message })
    );
  }

  return res
    .status(200)
    .json(buildSuccessResult({ storeId, shelfId, mlResult, catalog }));
});

module.exports = router;
