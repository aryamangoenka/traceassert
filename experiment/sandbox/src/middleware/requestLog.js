// tiny request logger, silent during tests
function requestLog(req, res, next) {
  if (process.env.NODE_ENV !== "test" && !process.env.VITEST) {
    console.log(`${req.method} ${req.path}`);
  }
  next();
}

module.exports = { requestLog };
