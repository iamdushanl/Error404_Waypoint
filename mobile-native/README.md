# Waypoint Driver Native

React Native / Expo source for the driver workflow. The browser `mobile/` target is the verified visual preview; this folder is the native runtime entrypoint for Android and iOS.

```bash
npm install
npx expo start
```

`api.ts` provides the native integration boundary: passwordless Supabase OTP, authenticated FastAPI requests, an AsyncStorage queue, stable operation IDs, and `/api/v1/sync` replay. Use it from the screen transitions when wiring native navigation to the same trip/delivery contracts as the browser driver app.
