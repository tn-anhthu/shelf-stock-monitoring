const express = require('express');
const fs = require('node:fs');
const path = require('node:path');
const multer = require('multer');
const { scansDb } = require('../services/scansDb');
const { isActiveShelf } = require('../config/shelfRegistry');
const { getUploadsDir } = require('../config/uploadsDir');

const router = express.Router();

const SCAN_ID_PATTERN = /^[A-Za-z0-9_-]+$/;

function isValidScanId(scanId) {
  return typeof scanId === 'string' && SCAN_ID_PATTERN.test(scanId);
}

function validateScanIdParam(req, res, next) {
  if (!isValidScanId(req.params.scanId)) {
    return res.status(400).json({ error: 'invalid scan_id' });
  }
  next();
}

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

  if (!isValidScanId(scanId)) {
    return res.status(400).json({ error: 'scan_id must contain only letters, digits, - and _' });
  }

  if (!isActiveShelf(category, container)) {
    return res.status(400).json({ error: 'category/container is missing or not active' });
  }

  const quantitiesWithSource = quantities.map((q) => ({ ...q, source: q.source ?? 'scan' }));
  const safeBoxes = Array.isArray(boxes) ? boxes : undefined;

  scansDb.insertScan({
    scanId,
    category,
    container,
    quantities: quantitiesWithSource,
    totalValue: totalValue ?? 0,
    boxes: safeBoxes,
  });

  return res.status(200).json({ confirmed: true, scan_id: scanId });
});

const imageUpload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => {
      const dir = getUploadsDir();
      fs.mkdirSync(dir, { recursive: true });
      cb(null, dir);
    },
    // Always force .jpg -- the crop pipeline (CropStep.jsx) only ever emits
    // image/jpeg, and this keeps any client-controlled segment out of the
    // filename written on the server.
    filename: (req, file, cb) => cb(null, `${req.params.scanId}.jpg`),
  }),
});

router.post('/confirm/:scanId/image', validateScanIdParam, imageUpload.single('image'), (req, res) => {
  const { scanId } = req.params;
  const scan = scansDb.getScanById(scanId);

  if (!scan) {
    if (req.file) fs.unlinkSync(req.file.path);
    return res.status(404).json({ error: 'scan not found' });
  }
  if (!req.file) {
    return res.status(400).json({ error: 'image is required' });
  }

  const imageWidth = Number(req.body.width);
  const imageHeight = Number(req.body.height);
  if (!Number.isFinite(imageWidth) || !Number.isFinite(imageHeight) || imageWidth <= 0 || imageHeight <= 0) {
    fs.unlinkSync(req.file.path);
    return res.status(400).json({ error: 'width and height are required and must be positive numbers' });
  }

  scansDb.setScanImage(scanId, { imagePath: req.file.filename, imageWidth, imageHeight });
  return res.status(200).json({ saved: true, image_path: req.file.filename });
});

module.exports = router;
