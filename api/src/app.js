const express = require('express');
const path = require('node:path');
const { getUploadsDir } = require('./config/uploadsDir');
const analyzeRouter = require('./routes/analyze');
const catalogRouter = require('./routes/catalog');
const confirmRouter = require('./routes/confirm');
const shelvesRouter = require('./routes/shelves');
const dashboardRouter = require('./routes/dashboard');

const app = express();

app.use(express.json());
app.use(express.static(path.resolve(__dirname, '..', '..', 'web', 'dist')));
// Re-read getUploadsDir() on every request (don't cache the path at app
// startup) so tests can point UPLOADS_DIR at a fresh temp directory.
app.use('/uploads', (req, res, next) => express.static(getUploadsDir())(req, res, next));
app.use(analyzeRouter);
app.use(catalogRouter);
app.use(confirmRouter);
app.use(shelvesRouter);
app.use(dashboardRouter);

module.exports = app;
