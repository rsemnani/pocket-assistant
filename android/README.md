# Pocket Assistant — Android app

Kiosk-style voice-capture client (Kotlin + Jetpack Compose). Targets the Nextbit Robin
(Android 7.1.1 / API 25): `minSdk 24`, `compileSdk 34`.

## Capture loop

Hold the big button → record (16 kHz mono) → on-device **Vosk** transcription → editable
transcript with a **5-second auto-send countdown** (Send / Edit / Cancel) → upload to the
backend → review proposed actions → approve/reject (PIN for sensitive actions) →
daily-summary view with text-to-speech.

## Prerequisites (this Mac)

The toolchain is installed via Homebrew (JDK 17 + Android cmdline-tools). Build commands
source a git-ignored `android/.build-env.sh` that sets `JAVA_HOME`/`ANDROID_HOME`.

## One-time: fetch the Vosk model

The ~40 MB English model is not committed. Fetch it into `app/src/main/assets/model/en-us`:

```bash
./scripts/fetch-vosk-model.sh   # from the repo root
```

## Build & install to the connected Robin

```bash
cd android
source .build-env.sh
./gradlew :app:installDebug      # builds + installs over USB (adb)
adb shell monkey -p com.pocketassistant.app.debug 1   # launch
adb logcat | grep -i pocket      # logs
```

## First run

1. The app opens on the **Pairing** screen.
2. Set the **Backend URL** (LAN `http://<mini-ip>:8000`, or a Tailscale name when remote).
3. Generate a registration code on the backend and enter it to pair (the device token is
   stored in the Android Keystore).
4. Grant the microphone permission, then hold to record.

> The default backend URL in `BuildConfig` is a placeholder (`10.0.2.2:8000`, the emulator
> host alias). Set your real URL in-app — no host/IP is committed to source.

## Notes

- STT is behind a `Transcriber` interface; a server-side implementation can replace Vosk
  later without touching callers.
- Backend request bodies are never logged (transcripts/email stay out of logs).
