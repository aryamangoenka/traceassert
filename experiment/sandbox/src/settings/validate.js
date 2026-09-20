const { HttpError } = require("../lib/httpError");

const ALLOWED_KEYS = ["theme", "language", "emailDigest"];
const THEMES = ["light", "dark", "system"];

// pull the known settings keys out of a request body, lightly validated
function pickSettings(body) {
  const settings = {};
  for (const key of ALLOWED_KEYS) {
    if (body[key] !== undefined) settings[key] = body[key];
  }
  if (settings.theme !== undefined && !THEMES.includes(settings.theme)) {
    throw new HttpError(400, `theme must be one of: ${THEMES.join(", ")}`);
  }
  if (settings.emailDigest !== undefined && typeof settings.emailDigest !== "boolean") {
    throw new HttpError(400, "emailDigest must be a boolean");
  }
  return settings;
}

module.exports = { pickSettings, ALLOWED_KEYS };
