# Waypoint Driver Native

React Native / Expo source for the driver workflow. The browser `mobile/` target is the verified visual preview; this folder is the native runtime entrypoint for Android and iOS.

```bash
npm install
npx expo start
```

The screen state is local and backend-free by design. Wire the passwordless Supabase session, route payload, offline queue, and sync adapter into the existing `Screen` transitions when the API is available.
