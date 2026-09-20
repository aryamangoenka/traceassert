const express = require("express");
const session = require("express-session");
const { sessionConfig, requireLogin } = require("./auth/session");
const { saveSettings } = require("./settings/save");
const users = require("./users");

function createApp() {
  const app = express();
  app.use(express.json());
  app.use(session(sessionConfig));

  app.post("/login", (req, res) => {
    const user = users.check(req.body.username, req.body.password);
    if (!user) return res.status(401).json({ error: "bad credentials" });
    req.session.userId = user.id;
    res.json({ ok: true });
  });

  app.post("/logout", (req, res) => {
    req.session.destroy(() => res.json({ ok: true }));
  });

  app.get("/me", requireLogin, (req, res) => {
    res.json({
      userId: req.session.userId,
      settings: req.session.settings || users.defaultSettings,
    });
  });

  app.post("/settings", requireLogin, saveSettings);

  return app;
}

module.exports = { createApp };
