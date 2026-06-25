package com.pocketassistant.app.net

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PATCH
import retrofit2.http.Path

/** Retrofit interface for the Pocket Assistant backend (v1). */
interface ApiService {

    @POST("/v1/devices/register")
    suspend fun register(@Body body: DeviceRegisterRequest): DeviceRegisterResponse

    @POST("/v1/devices/session/pin")
    suspend fun openSession(@Body body: SessionPinRequest): SessionPinResponse

    @POST("/v1/captures")
    suspend fun createCapture(
        @Body body: CaptureCreateRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): CaptureResponse

    @PATCH("/v1/captures/{id}/transcript")
    suspend fun editTranscript(
        @Path("id") captureId: String,
        @Body body: CaptureCreateRequest,
    ): CaptureResponse

    @POST("/v1/captures/{id}/interpret")
    suspend fun interpret(@Path("id") captureId: String): ProposalListResponse

    @POST("/v1/proposals/{id}/approve")
    suspend fun approve(
        @Path("id") actionId: String,
        @Header("X-Session-Token") sessionToken: String?,
    ): ApproveResponse

    @POST("/v1/proposals/{id}/reject")
    suspend fun reject(@Path("id") actionId: String): ApproveResponse

    @GET("/v1/summary/daily")
    suspend fun dailySummary(): DailySummaryResponse
}
