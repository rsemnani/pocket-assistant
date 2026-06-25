package com.pocketassistant.app.net

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.pocketassistant.app.data.SecureStore
import com.pocketassistant.app.data.SettingsStore
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

/**
 * Builds an [ApiService] bound to the currently configured backend URL, injecting the
 * device token as a Bearer header. Rebuilt lazily when the backend URL changes so the app
 * can be re-pointed (LAN vs Tailscale) without a restart.
 */
class ApiClient(
    private val settings: SettingsStore,
    private val secureStore: SecureStore,
) {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    @Volatile private var cachedUrl: String? = null
    @Volatile private var cachedService: ApiService? = null

    fun service(): ApiService {
        val url = settings.backendUrl
        val existing = cachedService
        if (existing != null && url == cachedUrl) return existing
        val built = build(url)
        cachedService = built
        cachedUrl = url
        return built
    }

    private fun build(baseUrl: String): ApiService {
        val authInterceptor = okhttp3.Interceptor { chain ->
            val builder = chain.request().newBuilder()
            secureStore.deviceToken?.let { builder.header("Authorization", "Bearer $it") }
            chain.proceed(builder.build())
        }
        val logging = HttpLoggingInterceptor().apply {
            // Redact bodies: transcripts/email content must not hit logs. Headers only.
            level = HttpLoggingInterceptor.Level.BASIC
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .baseUrl(ensureTrailingSlash(baseUrl))
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
            .create(ApiService::class.java)
    }

    private fun ensureTrailingSlash(url: String): String =
        if (url.endsWith("/")) url else "$url/"
}
