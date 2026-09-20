// session and auth configuration.
const SESSION_TIMEOUT = 15 * 60 * 1000; // fifteen minutes

const sessionConfig = {
  secret: "dev-secret-not-for-prod",
  resave: false,
  saveUninitialized: false,
  rolling: true,
  cookie: { maxAge: SESSION_TIMEOUT },
};

function requireLogin(req, res, next) {
  if (!req.session.userId) {
    return res.status(401).json({ error: "not logged in" });
  }
  next();
}

module.exports = { sessionConfig, requireLogin, SESSION_TIMEOUT };
