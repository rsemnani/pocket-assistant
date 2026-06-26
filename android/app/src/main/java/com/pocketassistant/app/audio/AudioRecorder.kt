package com.pocketassistant.app.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.RandomAccessFile

/**
 * Records 16 kHz mono 16-bit PCM from the microphone (Vosk-friendly). Captured PCM is kept
 * in memory for transcription and also written to a temporary WAV file (the on-device audio
 * cache, deleted after the capture is confirmed by the backend).
 */
class AudioRecorder {
    @Volatile private var recording = false
    private var record: AudioRecord? = null
    private var thread: Thread? = null
    private val buffer = ByteArrayOutputStream()

    val sampleRate = 16_000

    @SuppressLint("MissingPermission") // permission is checked by the caller before start()
    fun start() {
        if (recording) return
        buffer.reset()
        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufSize = if (minBuf > 0) minBuf * 2 else sampleRate
        val rec = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufSize,
        )
        record = rec
        recording = true
        rec.startRecording()
        thread = Thread {
            val chunk = ByteArray(bufSize)
            while (recording) {
                val n = rec.read(chunk, 0, chunk.size)
                if (n > 0) buffer.write(chunk, 0, n)
            }
        }.also { it.start() }
    }

    /** Stops recording and returns the captured PCM bytes. */
    fun stop(): ByteArray {
        if (!recording) return buffer.toByteArray()
        recording = false
        try {
            thread?.join(1_000)
        } catch (_: InterruptedException) {
        }
        record?.run {
            try {
                stop()
            } catch (_: IllegalStateException) {
            }
            release()
        }
        record = null
        thread = null
        return buffer.toByteArray()
    }

    /** Writes PCM as a WAV file (44-byte header + data) to the given path. */
    fun writeWav(pcm: ByteArray, file: File) {
        RandomAccessFile(file, "rw").use { out ->
            out.setLength(0)
            val totalDataLen = 36 + pcm.size
            val byteRate = sampleRate * 1 * 16 / 8
            out.write(wavHeader(totalDataLen, pcm.size, sampleRate, 1, byteRate))
            out.write(pcm)
        }
    }

    private fun wavHeader(
        totalDataLen: Int,
        audioDataLen: Int,
        sampleRate: Int,
        channels: Int,
        byteRate: Int,
    ): ByteArray {
        val h = ByteArray(44)
        fun put(i: Int, s: String) = s.forEachIndexed { k, c -> h[i + k] = c.code.toByte() }
        fun putIntLE(i: Int, v: Int) {
            h[i] = (v and 0xff).toByte()
            h[i + 1] = (v shr 8 and 0xff).toByte()
            h[i + 2] = (v shr 16 and 0xff).toByte()
            h[i + 3] = (v shr 24 and 0xff).toByte()
        }
        fun putShortLE(i: Int, v: Int) {
            h[i] = (v and 0xff).toByte()
            h[i + 1] = (v shr 8 and 0xff).toByte()
        }
        put(0, "RIFF"); putIntLE(4, totalDataLen); put(8, "WAVE")
        put(12, "fmt "); putIntLE(16, 16); putShortLE(20, 1)
        putShortLE(22, channels); putIntLE(24, sampleRate); putIntLE(28, byteRate)
        putShortLE(32, channels * 16 / 8); putShortLE(34, 16)
        put(36, "data"); putIntLE(40, audioDataLen)
        return h
    }
}
