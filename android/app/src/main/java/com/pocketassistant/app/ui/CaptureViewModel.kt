package com.pocketassistant.app.ui

import android.app.Application
import android.speech.tts.TextToSpeech
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.pocketassistant.app.PocketApp
import com.pocketassistant.app.audio.AudioRecorder
import com.pocketassistant.app.audio.Feedback
import com.pocketassistant.app.net.CaptureCreateRequest
import com.pocketassistant.app.net.DeviceRegisterRequest
import com.pocketassistant.app.net.ProposedActionDto
import com.pocketassistant.app.net.SessionPinRequest
import com.pocketassistant.app.net.DailySummaryResponse
import com.pocketassistant.app.stt.VoskTranscriber
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File
import java.util.Locale
import java.util.UUID

enum class Screen { PAIRING, HOME, REVIEW, PROPOSALS, SUMMARY, SETTINGS }

data class UiState(
    val screen: Screen = Screen.HOME,
    val paired: Boolean = false,
    val backendUrl: String = "",
    val recording: Boolean = false,
    val transcribing: Boolean = false,
    val modelReady: Boolean = false,
    val transcript: String = "",
    // The original on-device STT output, kept distinct from the (possibly edited) transcript
    // so the backend can log raw vs edited pairs for improving transcription.
    val transcriptRaw: String = "",
    val countdown: Int = 0,
    val captureId: String? = null,
    val intent: String? = null,
    val proposals: List<ProposedActionDto> = emptyList(),
    val pendingPinActionId: String? = null,
    val summary: DailySummaryResponse? = null,
    val busy: Boolean = false,
    val message: String? = null,
)

private const val AUTO_SEND_SECONDS = 5
private const val MORNING_SUMMARY_HOUR = 5

class CaptureViewModel(app: Application) : AndroidViewModel(app) {
    private val pocket = app as PocketApp
    private val recorder = AudioRecorder()
    private val feedback = Feedback(app)
    private val transcriber = VoskTranscriber(app)

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var countdownJob: Job? = null
    private var lastPcm: ByteArray = ByteArray(0)

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    init {
        val paired = pocket.secureStore.isPaired
        _state.update {
            it.copy(
                paired = paired,
                screen = if (paired) Screen.HOME else Screen.PAIRING,
                backendUrl = pocket.settings.backendUrl,
            )
        }
        viewModelScope.launch {
            val ready = transcriber.prepare()
            _state.update {
                it.copy(
                    modelReady = ready,
                    message = if (ready) it.message else "Voice model not found — run fetch-vosk-model.sh and reinstall.",
                )
            }
        }
        tts = TextToSpeech(app) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            tts?.language = Locale.US
        }
        maybeShowMorningSummary()
    }

    /** Proactively show + speak the daily summary on the first app open each morning. */
    private fun maybeShowMorningSummary() {
        if (!pocket.secureStore.isPaired) return
        val cal = java.util.Calendar.getInstance()
        if (cal.get(java.util.Calendar.HOUR_OF_DAY) < MORNING_SUMMARY_HOUR) return
        val today = java.text.SimpleDateFormat("yyyy-MM-dd", Locale.US).format(java.util.Date())
        if (pocket.settings.lastMorningSummaryDate == today) return
        pocket.settings.lastMorningSummaryDate = today
        loadSummary() // fetches, shows, and speaks the summary
    }

    // ── Pairing / settings ──────────────────────────────────────────────────────
    fun pair(url: String, code: String) = launchBusy {
        pocket.settings.backendUrl = url
        val resp = pocket.apiClient.service().register(DeviceRegisterRequest(registrationCode = code))
        pocket.secureStore.deviceToken = resp.deviceToken
        _state.update {
            it.copy(paired = true, screen = Screen.HOME, backendUrl = pocket.settings.backendUrl)
        }
    }

    fun saveBackendUrl(url: String) {
        pocket.settings.backendUrl = url
        _state.update { it.copy(backendUrl = pocket.settings.backendUrl) }
    }

    fun goTo(screen: Screen) = _state.update { it.copy(screen = screen, message = null) }

    // ── Recording ───────────────────────────────────────────────────────────────
    fun onRecordStart() {
        if (_state.value.recording) return
        feedback.recordStart()
        recorder.start()
        _state.update { it.copy(recording = true, message = null) }
    }

    fun onRecordStop() {
        if (!_state.value.recording) return
        feedback.recordStop()
        val pcm = recorder.stop()
        lastPcm = pcm
        _state.update { it.copy(recording = false, transcribing = true) }
        viewModelScope.launch {
            cacheAudio(pcm)
            val text = runCatching { transcriber.transcribe(pcm) }.getOrDefault("")
            _state.update {
                it.copy(
                    transcribing = false,
                    transcript = text,
                    transcriptRaw = text, // capture the original STT before any edits
                    screen = Screen.REVIEW,
                )
            }
            startCountdown()
        }
    }

    private fun cacheAudio(pcm: ByteArray) {
        runCatching {
            val dir = File(getApplication<Application>().cacheDir, "audio").apply { mkdirs() }
            recorder.writeWav(pcm, File(dir, "capture-${System.currentTimeMillis()}.wav"))
        }
    }

    // ── Review + 5s auto-send countdown ─────────────────────────────────────────
    private fun startCountdown() {
        countdownJob?.cancel()
        countdownJob = viewModelScope.launch {
            for (s in AUTO_SEND_SECONDS downTo 1) {
                _state.update { it.copy(countdown = s) }
                delay(1_000)
            }
            _state.update { it.copy(countdown = 0) }
            send()
        }
    }

    private fun cancelCountdown() {
        countdownJob?.cancel()
        countdownJob = null
        if (_state.value.countdown != 0) _state.update { it.copy(countdown = 0) }
    }

    /** Called when the transcript field gains focus — starting to edit cancels auto-send. */
    fun onTranscriptFocused() = cancelCountdown()

    fun onEditTranscript(text: String) {
        cancelCountdown()
        _state.update { it.copy(transcript = text) }
    }

    fun onCancelReview() {
        countdownJob?.cancel()
        _state.update {
            it.copy(
                screen = Screen.HOME,
                transcript = "",
                transcriptRaw = "",
                countdown = 0,
                captureId = null,
            )
        }
    }

    // ── Send → interpret → proposals ────────────────────────────────────────────
    fun send() {
        countdownJob?.cancel()
        val transcript = _state.value.transcript.trim()
        if (transcript.isEmpty()) {
            _state.update { it.copy(message = "Nothing to send.") }
            return
        }
        val rawStt = _state.value.transcriptRaw.trim()
        launchBusy {
            val svc = pocket.apiClient.service()
            val capture = svc.createCapture(
                CaptureCreateRequest(
                    transcript = transcript,
                    // Send the original STT only when it differs (i.e. the user edited it).
                    transcriptRaw = rawStt.takeIf { it.isNotEmpty() && it != transcript },
                ),
                idempotencyKey = UUID.randomUUID().toString(),
            )
            val proposals = svc.interpret(capture.id)
            // A daily-summary request is read-only: fetch, show, and speak it directly
            // instead of surfacing an approval card.
            if (proposals.intent == "daily_summary") {
                val summary = pocket.apiClient.service().dailySummary()
                _state.update {
                    it.copy(
                        captureId = capture.id,
                        intent = proposals.intent,
                        summary = summary,
                        screen = Screen.SUMMARY,
                        countdown = 0,
                    )
                }
                speak(summary.spokenText)
            } else {
                _state.update {
                    it.copy(
                        captureId = capture.id,
                        intent = proposals.intent,
                        proposals = proposals.actions,
                        screen = Screen.PROPOSALS,
                        countdown = 0,
                    )
                }
            }
        }
    }

    // ── Approvals (with PIN gating) ──────────────────────────────────────────────
    fun approve(action: ProposedActionDto) {
        val now = System.currentTimeMillis()
        val needsPin = action.sensitivity == "pin_required"
        if (needsPin && !pocket.secureStore.hasValidSession(now)) {
            _state.update { it.copy(pendingPinActionId = action.id) }
            return
        }
        doApprove(action.id)
    }

    private fun doApprove(actionId: String) = launchBusy {
        val now = System.currentTimeMillis()
        val sessionToken =
            if (pocket.secureStore.hasValidSession(now)) pocket.secureStore.sessionToken else null
        pocket.apiClient.service().approve(actionId, sessionToken)
        markActionStatus(actionId, "executed")
    }

    fun reject(action: ProposedActionDto) = launchBusy {
        pocket.apiClient.service().reject(action.id)
        markActionStatus(action.id, "rejected")
    }

    fun submitPin(pin: String) = launchBusy {
        val resp = pocket.apiClient.service().openSession(SessionPinRequest(pin))
        pocket.secureStore.sessionToken = resp.sessionToken
        // The server enforces the real expiry; locally we keep a conservative hint so the
        // app re-prompts for a PIN in good time. (Avoids API 26+ java.time on minSdk 24.)
        pocket.secureStore.sessionExpiresAtEpochMs = System.currentTimeMillis() + 14 * 60_000
        val pending = _state.value.pendingPinActionId
        _state.update { it.copy(pendingPinActionId = null) }
        if (pending != null) doApprove(pending)
    }

    fun dismissPin() = _state.update { it.copy(pendingPinActionId = null) }

    private fun markActionStatus(actionId: String, status: String) {
        _state.update { s ->
            s.copy(proposals = s.proposals.map { if (it.id == actionId) it.copy(status = status) else it })
        }
    }

    // ── Daily summary ────────────────────────────────────────────────────────────
    fun loadSummary(speak: Boolean = true) = launchBusy {
        val summary = pocket.apiClient.service().dailySummary()
        _state.update { it.copy(summary = summary, screen = Screen.SUMMARY) }
        if (speak) speak(summary.spokenText)
    }

    fun speakSummary() {
        _state.value.summary?.let { speak(it.spokenText) }
    }

    private fun speak(text: String) {
        if (ttsReady && text.isNotBlank()) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "summary")
        }
    }

    // ── helpers ──────────────────────────────────────────────────────────────────
    private fun launchBusy(block: suspend () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, message = null) }
            try {
                block()
            } catch (e: Exception) {
                _state.update { it.copy(message = friendlyError(e)) }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    private fun friendlyError(e: Exception): String {
        val raw = e.message ?: e.javaClass.simpleName
        return when {
            raw.contains("401") -> "Not authorized — re-pair the device in Settings."
            raw.contains("403") -> "PIN required or incorrect."
            raw.contains("Failed to connect") || raw.contains("timeout", true) ->
                "Can't reach the backend at ${pocket.settings.backendUrl}. Check the URL/network."
            else -> "Error: $raw"
        }
    }

    override fun onCleared() {
        tts?.shutdown()
        super.onCleared()
    }
}
