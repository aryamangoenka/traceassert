const { HttpError } = require("../lib/httpError");

// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  const status = err instanceof HttpError ? err.status : 500;
  res.status(status).json({ error: err.message || "internal error" });
}

module.exports = { errorHandler };
