# Rasheed — Mobile App

The Flutter client for **Rasheed**, an AI-powered expense-tracking and
savings app. See the [root README](../README.md) for the full picture —
what the app does, the architecture, and how to run the backend it talks to.
This file only covers what's specific to the mobile side.

## Setup

```bash
flutter pub get
flutter run
```

By default the app points at `http://10.0.2.2:8000` — the Android
emulator's alias for `localhost` on your host machine, where the backend
(see root README) is expected to be running via Docker Compose.

To run on a **physical device**, or a device on a different network, update
`kApiBaseUrl` in `lib/core/api_client.dart` to point at a reachable address
for the backend (your machine's LAN IP, or a tunnel like ngrok for testing
on a remote device).

## Android permissions

A few features need runtime permissions declared in
`android/app/src/main/AndroidManifest.xml`:

| Feature | Permission |
|---|---|
| Receipt scanning (OCR) | `CAMERA`, `READ_MEDIA_IMAGES` |
| Bank SMS import | `READ_SMS` |
| Text-to-speech | none (but needs a `TTS_SERVICE` entry under `<queries>` on Android 11+) |

The app requests these at runtime and degrades gracefully (with an in-app
message) if a permission is denied — none of them are required just to use
the app's core features.

## Project structure

```
lib/
├── core/       # Riverpod providers, API client config
├── models/     # data classes mirroring the backend's API responses
├── services/    # one file per API domain (goals, transactions, agent...)
├── screens/     # one folder per screen
├── widgets/      # shared/reusable widgets
└── theme/         # colors, personas' visual identity (icons, mood colors)
```

## Notes

- State management: [Riverpod](https://riverpod.dev/).
- No local persistence beyond the JWT (via `flutter_secure_storage`) — all
  other data is fetched from the backend on each screen load.