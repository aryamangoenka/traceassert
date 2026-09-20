const config = require("../config");
const { HttpError } = require("../lib/httpError");

// notes per user id, in memory
const notesByUser = new Map();
let nextId = 1;

function list(userId) {
  return notesByUser.get(userId) || [];
}

function create(userId, text) {
  if (typeof text !== "string" || !text.trim()) {
    throw new HttpError(400, "note text is required");
  }
  if (text.length > config.maxNoteLength) {
    throw new HttpError(400, "note too long");
  }
  const notes = notesByUser.get(userId) || [];
  if (notes.length >= config.maxNotesPerUser) {
    throw new HttpError(400, "too many notes");
  }
  const note = { id: nextId++, text, createdAt: new Date().toISOString() };
  notes.push(note);
  notesByUser.set(userId, notes);
  return note;
}

function remove(userId, noteId) {
  const notes = notesByUser.get(userId) || [];
  const idx = notes.findIndex((n) => n.id === noteId);
  if (idx === -1) throw new HttpError(404, "note not found");
  notes.splice(idx, 1);
}

module.exports = { list, create, remove };
