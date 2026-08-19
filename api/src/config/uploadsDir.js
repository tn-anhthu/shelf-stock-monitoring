const path = require('node:path');

function getUploadsDir() {
  return process.env.UPLOADS_DIR || path.resolve(__dirname, '..', '..', 'uploads');
}

module.exports = { getUploadsDir };
