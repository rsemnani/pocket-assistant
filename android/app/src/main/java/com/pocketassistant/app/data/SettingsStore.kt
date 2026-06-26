package com.pocketassistant.app.data

import android.content.Context
import com.pocketassistant.app.BuildConfig

/**
 * Non-secret app settings (backend base URL). Backed by plain SharedPreferences.
 * The default URL comes from BuildConfig (a placeholder) and is overridable in-app, so no
 * real host/IP is ever committed to source.
 */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("pocket_settings", Context.MODE_PRIVATE)

    var backendUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, BuildConfig.DEFAULT_BACKEND_URL)
            ?: BuildConfig.DEFAULT_BACKEND_URL
        set(value) = prefs.edit().putString(KEY_BACKEND_URL, normalize(value)).apply()

    private fun normalize(url: String): String =
        url.trim().removeSuffix("/")

    companion object {
        private const val KEY_BACKEND_URL = "backend_url"
    }
}
