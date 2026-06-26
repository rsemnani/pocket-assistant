package com.pocketassistant.app.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Encrypted storage for the long-lived device token and the short-lived session token.
 * Backed by the Android Keystore via Jetpack Security. The raw PIN is never stored — only
 * the session token returned by the backend after a successful PIN unlock.
 */
class SecureStore(context: Context) {
    private val prefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "pocket_secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var deviceToken: String?
        get() = prefs.getString(KEY_DEVICE_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_DEVICE_TOKEN, value).apply()

    var sessionToken: String?
        get() = prefs.getString(KEY_SESSION_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_SESSION_TOKEN, value).apply()

    var sessionExpiresAtEpochMs: Long
        get() = prefs.getLong(KEY_SESSION_EXPIRES, 0L)
        set(value) = prefs.edit().putLong(KEY_SESSION_EXPIRES, value).apply()

    val isPaired: Boolean get() = !deviceToken.isNullOrBlank()

    fun hasValidSession(nowMs: Long): Boolean =
        !sessionToken.isNullOrBlank() && sessionExpiresAtEpochMs > nowMs

    fun clearSession() {
        prefs.edit().remove(KEY_SESSION_TOKEN).remove(KEY_SESSION_EXPIRES).apply()
    }

    fun unpair() {
        prefs.edit().clear().apply()
    }

    companion object {
        private const val KEY_DEVICE_TOKEN = "device_token"
        private const val KEY_SESSION_TOKEN = "session_token"
        private const val KEY_SESSION_EXPIRES = "session_expires"
    }
}
