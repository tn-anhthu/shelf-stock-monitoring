const express = require('express');
const path = require('node:path');
const analyzeRouter = require('./routes/analyze');

const app = express();

app.use(express.static(path.resolve(__dirname, '..', '..', 'web')));
app.use(analyzeRouter);

module.exports = app;
