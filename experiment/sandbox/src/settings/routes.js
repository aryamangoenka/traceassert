const express = require("express");
const { requireLogin } = require("../auth/session");
const users = require("../users/store");
const { pickSettings } = require("./validate");
const { persistSettings, currentSettings } = require("./service");

const router = express.Router();
router.use(requireLogin);

router.get("/", (req, res) => {
  res.json({ settings: currentSettings(req, users.defaultSettings) });
});

router.post("/", (req, res, next) => {
  let settings;
  try {
    settings = pickSettings(req.body);
  } catch (err) {
    return next(err);
  }
  persistSettings(req, settings, (err) => {
    if (err) return next(err);
    res.json({ ok: true, settings });
  });
});

module.exports = router;
