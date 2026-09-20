const express = require("express");
const { requireLogin } = require("../auth/session");
const store = require("./store");

const router = express.Router();
router.use(requireLogin);

router.get("/", (req, res) => {
  res.json({ notes: store.list(req.session.userId) });
});

router.post("/", (req, res, next) => {
  try {
    const note = store.create(req.session.userId, req.body.text);
    res.status(201).json({ note });
  } catch (err) {
    next(err);
  }
});

router.delete("/:id", (req, res, next) => {
  try {
    store.remove(req.session.userId, Number(req.params.id));
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
