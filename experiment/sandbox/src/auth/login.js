const users = require("../users/store");

function login(req, res) {
  const user = users.check(req.body.username, req.body.password);
  if (!user) return res.status(401).json({ error: "bad credentials" });
  req.session.userId = user.id;
  res.json({ ok: true });
}

function logout(req, res) {
  req.session.destroy(() => res.json({ ok: true }));
}

module.exports = { login, logout };
