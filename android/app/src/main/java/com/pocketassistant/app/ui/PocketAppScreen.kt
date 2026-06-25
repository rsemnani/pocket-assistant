package com.pocketassistant.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

/** Top-level state-driven router. Keeps navigation simple and predictable for a kiosk. */
@Composable
fun PocketAppScreen(vm: CaptureViewModel, micGranted: Boolean, onRequestMic: () -> Unit) {
    val state by vm.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.message) {
        state.message?.let { snackbar.showSnackbar(it) }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            when (state.screen) {
                Screen.PAIRING -> PairingScreen(state, onPair = vm::pair)
                Screen.HOME -> HomeScreen(
                    state = state,
                    micGranted = micGranted,
                    onRequestMic = onRequestMic,
                    onRecordStart = vm::onRecordStart,
                    onRecordStop = vm::onRecordStop,
                    onShowDay = { vm.loadSummary() },
                    onSettings = { vm.goTo(Screen.SETTINGS) },
                )
                Screen.REVIEW -> ReviewScreen(
                    state = state,
                    onEdit = vm::onEditTranscript,
                    onSend = vm::send,
                    onCancel = vm::onCancelReview,
                )
                Screen.PROPOSALS -> ProposalsScreen(
                    state = state,
                    onApprove = vm::approve,
                    onReject = vm::reject,
                    onPin = vm::submitPin,
                    onDismissPin = vm::dismissPin,
                    onDone = { vm.goTo(Screen.HOME) },
                )
                Screen.SUMMARY -> SummaryScreen(
                    state = state,
                    onSpeak = vm::speakSummary,
                    onDone = { vm.goTo(Screen.HOME) },
                )
                Screen.SETTINGS -> SettingsScreen(
                    state = state,
                    onSave = vm::saveBackendUrl,
                    onDone = { vm.goTo(Screen.HOME) },
                )
            }
            if (state.busy) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
        }
    }
}
