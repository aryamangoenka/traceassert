const express = require("express");
const session = require("express-session");
const { sessionConfig, requireLogin } = require("./auth/session");
const { login, logout } = require("./auth/login");
const { requestLog } = require("./middleware/requestLog");
const { errorHandler } = require("./middleware/errorHandler");
const notesRouter = require("./notes/routes");
const settingsRouter = require("./settings/routes");
const users = require("./users/store");
const config = require("./config");

function createApp() {
  const app = express();
  app.use(express.json());
  app.use(requestLog);
  app.use(session(sessionConfig));

  app.post("/login", login);
  app.post("/logout", logout);

  app.get("/me", requireLogin, (req, res) => {
    res.json({
      userId: req.session.userId,
      settings: req.session.settings || users.defaultSettings,
    });
  });

  app.use("/notes", notesRouter);
  app.use("/settings", settingsRouter);

  app.use(errorHandler);
  return app;
}

if (require.main === module) {
  createApp().listen(config.port, () => console.log(`notely on :${config.port}`));
}

module.exports = { createApp };
