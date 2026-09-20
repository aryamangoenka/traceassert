# notely

a small notes app with per-user settings. express + express-session, in-memory stores, this is a demo codebase.

- `POST /login`, `POST /logout`
- `GET /me` returns the current user and their settings
- `GET /notes`, `POST /notes`, `DELETE /notes/:id`
- `GET /settings`, `POST /settings`

run the tests:

```
npm test
```
