# Waypoint Frontends

Frontend-only implementation of the Waypoint Fresh delivery workflow.

- `web/`: role-aware web console for Store Manager, Dispatcher, and Loader.
- `mobile/`: verified phone-first Driver browser preview.
- `mobile-native/`: React Native / Expo Driver app entrypoint for Android and iOS.

Both apps use seeded in-memory/localStorage state so the UI can be exercised without Supabase or FastAPI. Authentication is represented by a passwordless email/phone flow and Google sign-in action; replace the marked adapter boundary with Supabase Auth when the backend is ready.

## Repository boundary

Commit and push this `codebase/` folder only. The sibling `screrns/` folder is the original Figma Make reference project and is not part of this implementation repository. Generated dependencies and build output are excluded by [.gitignore](.gitignore).

## Run

```bash
cd web && npm install && npm run dev
cd mobile && npm install && npm run dev
```

For the native driver app:

```bash
cd mobile-native && npm install && npx expo start
```

Build the verified web and mobile browser targets from this directory with `npm run build`. Backend integration guidance is in [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md).
