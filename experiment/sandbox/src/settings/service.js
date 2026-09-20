// persists the user's settings onto their session
function persistSettings(req, settings, done) {
  // regenerate the session id before writing new data
  req.session.regenerate((err) => {
    if (err) return done(err);
    req.session.settings = settings;
    req.session.save(done);
  });
}

function currentSettings(req, defaults) {
  return req.session.settings || defaults;
}

module.exports = { persistSettings, currentSettings };
