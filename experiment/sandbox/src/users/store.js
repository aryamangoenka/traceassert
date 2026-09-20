// in-memory user store, this is a demo app
const users = [
  { id: 1, username: "ada", password: "pw" },
  { id: 2, username: "grace", password: "pw2" },
];

const defaultSettings = { theme: "light", language: "en", emailDigest: true };

function check(username, password) {
  return users.find((u) => u.username === username && u.password === password) || null;
}

function byId(id) {
  return users.find((u) => u.id === id) || null;
}

module.exports = { check, byId, defaultSettings };
