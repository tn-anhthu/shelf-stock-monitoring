const express = require('express');
const path = require('node:path');
const analyzeRouter = require('./routes/analyze');
const catalogRouter = require('./routes/catalog');
const confirmRouter = require('./routes/confirm');
const shelvesRouter = require('./routes/shelves');
const dashboardRouter = require('./routes/dashboard');

const app = express();

app.use(express.json());
app.use(express.static(path.resolve(__dirname, '..', '..', 'web', 'dist')));
app.use(analyzeRouter);
app.use(catalogRouter);
app.use(confirmRouter);
app.use(shelvesRouter);
app.use(dashboardRouter);

module.exports = app;
