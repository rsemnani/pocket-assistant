package com.pocketassistant.app.stt

/**
 * Pluggable speech-to-text. The MVP uses an on-device Vosk implementation; a server-side
 * implementation can be added later behind this same interface without touching callers.
 */
interface Transcriber {
    /** Prepare any models/resources. Safe to call repeatedly; returns true when ready. */
    suspend fun prepare(): Boolean

    /** Transcribe 16 kHz mono 16-bit PCM and return recognized English text. */
    suspend fun transcribe(pcm: ByteArray): String

    val isReady: Boolean
}
