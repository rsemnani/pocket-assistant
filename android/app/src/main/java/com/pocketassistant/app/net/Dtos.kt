package com.pocketassistant.app.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Wire models mirroring the backend's Pydantic schemas (see backend/schemas/api.py).
 * Only the fields the app needs are modeled; unknown fields are ignored by the JSON config.
 */

@Serializable
data class DeviceRegisterRequest(
    @SerialName("registration_code") val registrationCode: String,
    val name: String = "Robin",
)

@Serializable
data class DeviceRegisterResponse(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_token") val deviceToken: String,
)

@Serializable
data class SessionPinRequest(val pin: String)

@Serializable
data class SessionPinResponse(
    @SerialName("session_token") val sessionToken: String,
    @SerialName("expires_at") val expiresAt: String,
)

@Serializable
data class CaptureCreateRequest(
    val transcript: String,
    // Original on-device STT output; sent only when the user edited the transcript.
    @SerialName("transcript_raw") val transcriptRaw: String? = null,
    @SerialName("transcription_source") val transcriptionSource: String = "device",
)

@Serializable
data class CaptureResponse(
    val id: String,
    val status: String,
    @SerialName("transcript_edited") val transcriptEdited: String? = null,
)

@Serializable
data class ProposedActionDto(
    val id: String,
    val type: String,
    val explanation: String,
    val sensitivity: String,
    val status: String,
)

@Serializable
data class ProposalListResponse(
    @SerialName("capture_id") val captureId: String,
    val intent: String,
    val actions: List<ProposedActionDto> = emptyList(),
)

@Serializable
data class ApproveResponse(
    @SerialName("action_id") val actionId: String,
    val status: String,
)

@Serializable
data class TaskDto(
    val id: String,
    val title: String,
    val status: String,
    val priority: String,
)

@Serializable
data class DailySummaryResponse(
    @SerialName("spoken_text") val spokenText: String,
    val tasks: List<TaskDto> = emptyList(),
    val overdue: List<TaskDto> = emptyList(),
    @SerialName("completion_prompts") val completionPrompts: List<String> = emptyList(),
)
