package com.pocketassistant.app.audio

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

/** Sound + haptic feedback for record start/stop and send/cancel. Honors silent mode. */
class Feedback(context: Context) {
    private val appContext = context.applicationContext

    private val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        (appContext.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)
            ?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        appContext.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    }

    private fun tone(type: Int, durationMs: Int) {
        try {
            val gen = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
            gen.startTone(type, durationMs)
            // Release shortly after the tone finishes.
            Thread {
                Thread.sleep((durationMs + 50).toLong())
                gen.release()
            }.start()
        } catch (_: RuntimeException) {
            // ToneGenerator can throw if audio resources are unavailable; ignore.
        }
    }

    private fun vibrate(ms: Long) {
        val v = vibrator ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            v.vibrate(ms)
        }
    }

    fun recordStart() {
        tone(ToneGenerator.TONE_PROP_BEEP, 120)
        vibrate(40)
    }

    fun recordStop() {
        tone(ToneGenerator.TONE_PROP_ACK, 150)
        vibrate(60)
    }

    fun light() = vibrate(20)
}
