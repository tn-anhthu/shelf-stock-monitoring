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
    // Stage to a unique temp name -- NOT the final <scanId>.jpg -- so a
    // failed/invalid re-upload can never overwrite (and then accidentally
    // delete) a previously-saved good image before validation completes.
    filename: (req, file, cb) => {
      cb(null, `${req.params.scanId}.upload-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    },
  }),
  limits: { fileSize: 20 * 1024 * 1024, files: 1 },
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

  // All validation has passed -- only now do we touch the final <scanId>.jpg
  // path, so a previously-saved good image is never overwritten (or deleted
  // on a subsequent validation failure) until the new upload is fully valid.
  const finalFilename = `${scanId}.jpg`;
  const finalPath = path.join(getUploadsDir(), finalFilename);
  fs.renameSync(req.file.path, finalPath);

  scansDb.setScanImage(scanId, { imagePath: finalFilename, imageWidth, imageHeight });
  return res.status(200).json({ saved: true, image_path: finalFilename });
});

router.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ error: err.message });
  }
  next(err);
});

module.exports = router;
