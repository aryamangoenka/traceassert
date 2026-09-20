# notely

a small notes app with per-user settings. express + express-session, in-memory stores, this is a demo codebase.

- `POST /login`, `POST /logout`
- `GET /me` returns the current user and their settings
- `POST /settings` saves settings for the logged-in user

run the tests:

```
npm test
```
