package com.pocketassistant.app

import android.app.Application
import com.pocketassistant.app.data.SecureStore
import com.pocketassistant.app.data.SettingsStore
import com.pocketassistant.app.net.ApiClient

/**
 * Application entry point. Holds process-wide singletons (settings, secure storage, API
 * client). Kept deliberately small — no DI framework for the MVP.
 */
class PocketApp : Application() {
    lateinit var settings: SettingsStore
        private set
    lateinit var secureStore: SecureStore
        private set
    lateinit var apiClient: ApiClient
        private set

    override fun onCreate() {
        super.onCreate()
        settings = SettingsStore(this)
        secureStore = SecureStore(this)
        apiClient = ApiClient(settings, secureStore)
    }
}
