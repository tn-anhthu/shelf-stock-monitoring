const express = require('express');
const path = require('node:path');
const analyzeRouter = require('./routes/analyze');
const catalogRouter = require('./routes/catalog');

const app = express();

app.use(express.static(path.resolve(__dirname, '..', '..', 'web', 'dist')));
app.use(analyzeRouter);
app.use(catalogRouter);

module.exports = app;
