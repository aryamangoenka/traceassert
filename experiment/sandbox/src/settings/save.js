const ALLOWED_KEYS = ["theme", "language", "emailDigest"];

// persist the user's settings onto their session
function saveSettings(req, res) {
  const settings = {};
  for (const key of ALLOWED_KEYS) {
    if (req.body[key] !== undefined) settings[key] = req.body[key];
  }

  // regenerate the session id before writing new data
  req.session.regenerate((err) => {
    if (err) return res.status(500).json({ error: "session error" });
    req.session.settings = settings;
    req.session.save(() => res.json({ ok: true, settings }));
  });
}

module.exports = { saveSettings };
