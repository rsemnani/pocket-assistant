# Android device testing (`@dev-pc`)

The Nextbit Robin is physically connected by USB to **`@dev-pc`** (this computer), not to
the mini computer. All Android build/install/debug happens here. (Phase 2.)

## Prerequisites

- Android Studio + JDK 17
- Android SDK platform-tools (`adb`)
- USB debugging enabled on the Robin

## Build & install (debug)

```bash
cd android
./gradlew installDebug      # builds and installs onto the connected Robin over USB
```

## Logs

```bash
adb logcat | grep -i pocket
```

## Pointing the app at the backend

The backend base URL is **configurable** (no hardcoded IPs in source):

- **Home LAN:** `http://<mini-lan-ip>:<port>`
- **Remote:** the `@mini` Tailscale tailnet name

Set it via the app's dev Settings screen or a build-config field — never commit a real
host/IP.

## Kiosk behavior (MVP)

The app behaves as a launcher/pinned full-screen app so that waking the phone brings the
capture screen forward. A stronger Device Owner / Lock Task kiosk is a later enhancement
(see `DESIGN.md` §22).
