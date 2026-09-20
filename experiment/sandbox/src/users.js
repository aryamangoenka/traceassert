// in-memory user store, this is a demo app
const users = [{ id: 1, username: "ada", password: "pw" }];

const defaultSettings = { theme: "light", language: "en", emailDigest: true };

function check(username, password) {
  return users.find((u) => u.username === username && u.password === password) || null;
}

module.exports = { check, defaultSettings };
