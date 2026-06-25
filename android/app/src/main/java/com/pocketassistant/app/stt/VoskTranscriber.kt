package com.pocketassistant.app.stt

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File

/**
 * On-device English transcription using Vosk. The model is bundled in assets under
 * `model/en-us` (fetched by scripts/fetch-vosk-model.sh, not committed) and unpacked to the
 * app's private files dir on first run.
 */
class VoskTranscriber(private val context: Context) : Transcriber {
    private var model: Model? = null

    override val isReady: Boolean get() = model != null

    override suspend fun prepare(): Boolean = withContext(Dispatchers.IO) {
        if (model != null) return@withContext true
        val dir = ensureModelUnpacked() ?: return@withContext false
        model = Model(dir.absolutePath)
        true
    }

    override suspend fun transcribe(pcm: ByteArray): String = withContext(Dispatchers.IO) {
        val m = model ?: (if (prepare()) model else null) ?: return@withContext ""
        val recognizer = Recognizer(m, 16_000.0f)
        try {
            val chunk = 4096
            var offset = 0
            while (offset < pcm.size) {
                val len = minOf(chunk, pcm.size - offset)
                recognizer.acceptWaveForm(pcm.copyOfRange(offset, offset + len), len)
                offset += len
            }
            JSONObject(recognizer.finalResult).optString("text", "").trim()
        } finally {
            recognizer.close()
        }
    }

    /** Copies the bundled model from assets to filesDir once; returns the unpacked dir. */
    private fun ensureModelUnpacked(): File? {
        val target = File(context.filesDir, "vosk-model-en-us")
        val marker = File(target, ".unpacked")
        if (marker.exists()) return target
        val assetRoot = "model/en-us"
        val assets = context.assets
        return try {
            if (assets.list(assetRoot).isNullOrEmpty()) return null
            copyAssetDir(assetRoot, target)
            marker.writeText("ok")
            target
        } catch (_: Exception) {
            null
        }
    }

    private fun copyAssetDir(assetPath: String, dest: File) {
        val entries = context.assets.list(assetPath) ?: return
        if (entries.isEmpty()) {
            // It's a file.
            dest.parentFile?.mkdirs()
            context.assets.open(assetPath).use { input ->
                dest.outputStream().use { input.copyTo(it) }
            }
            return
        }
        dest.mkdirs()
        for (entry in entries) {
            copyAssetDir("$assetPath/$entry", File(dest, entry))
        }
    }
}
