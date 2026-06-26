package com.pocketassistant.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.pocketassistant.app.net.ProposedActionDto

@Composable
fun HomeScreen(
    state: UiState,
    micGranted: Boolean,
    onRequestMic: () -> Unit,
    onRecordStart: () -> Unit,
    onRecordStop: () -> Unit,
    onShowDay: () -> Unit,
    onSettings: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = onShowDay) { Text("What's my day?") }
            TextButton(onClick = onSettings) { Text("Settings") }
        }

        val label = when {
            state.transcribing -> "Transcribing…"
            state.recording -> "Listening — release to stop"
            !micGranted -> "Tap to grant microphone"
            !state.modelReady -> "Hold to record (model loading)"
            else -> "Hold to record"
        }

        Box(
            Modifier
                .size(220.dp)
                .background(
                    if (state.recording) MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.primary,
                    CircleShape,
                )
                .pointerInput(micGranted) {
                    detectTapGestures(
                        onPress = {
                            if (!micGranted) {
                                onRequestMic()
                                return@detectTapGestures
                            }
                            onRecordStart()
                            tryAwaitRelease()
                            onRecordStop()
                        },
                    )
                },
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (state.recording) "● REC" else "🎤",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onPrimary,
            )
        }

        Text(label, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
fun ReviewScreen(
    state: UiState,
    onEdit: (String) -> Unit,
    onFocused: () -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("Review transcript", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = state.transcript,
            onValueChange = onEdit,
            modifier = Modifier
                .fillMaxWidth()
                .height(220.dp)
                .onFocusChanged { if (it.isFocused) onFocused() },
            label = { Text("Tap to edit — cancels auto-send") },
        )
        Spacer(Modifier.height(12.dp))
        if (state.countdown > 0) {
            Text(
                "Auto-sending in ${state.countdown}s…",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(12.dp))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = onSend, modifier = Modifier.weight(1f)) { Text("Send") }
            OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("Cancel") }
        }
    }
}

@Composable
fun ProposalsScreen(
    state: UiState,
    onApprove: (ProposedActionDto) -> Unit,
    onReject: (ProposedActionDto) -> Unit,
    onPin: (String) -> Unit,
    onDismissPin: () -> Unit,
    onDone: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("Proposed actions", style = MaterialTheme.typography.headlineSmall)
        state.intent?.let { Text("Intent: $it", style = MaterialTheme.typography.labelMedium) }
        Spacer(Modifier.height(12.dp))
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(state.proposals, key = { it.id }) { action ->
                ProposalCard(action, onApprove, onReject)
            }
        }
        Spacer(Modifier.height(12.dp))
        Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Done") }
    }

    state.pendingPinActionId?.let {
        PinDialog(onSubmit = onPin, onDismiss = onDismissPin)
    }
}

@Composable
private fun ProposalCard(
    action: ProposedActionDto,
    onApprove: (ProposedActionDto) -> Unit,
    onReject: (ProposedActionDto) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(action.explanation, style = MaterialTheme.typography.bodyLarge)
            Spacer(Modifier.height(4.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(action.type, style = MaterialTheme.typography.labelSmall)
                if (action.sensitivity == "pin_required") {
                    Text("🔒 PIN", style = MaterialTheme.typography.labelSmall)
                }
            }
            Spacer(Modifier.height(8.dp))
            when (action.status) {
                "executed", "approved" -> Text("✓ Approved", color = MaterialTheme.colorScheme.primary)
                "rejected" -> Text("✗ Rejected", color = MaterialTheme.colorScheme.error)
                else -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(onClick = { onApprove(action) }) { Text("Approve") }
                    OutlinedButton(onClick = { onReject(action) }) { Text("Reject") }
                }
            }
        }
    }
}

@Composable
private fun PinDialog(onSubmit: (String) -> Unit, onDismiss: () -> Unit) {
    var pin by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Confirm with PIN") },
        text = {
            OutlinedTextField(
                value = pin,
                onValueChange = { pin = it },
                label = { Text("Session PIN") },
                visualTransformation = PasswordVisualTransformation(),
            )
        },
        confirmButton = { TextButton(onClick = { onSubmit(pin) }) { Text("Confirm") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
fun SummaryScreen(state: UiState, onSpeak: () -> Unit, onDone: () -> Unit) {
    val summary = state.summary
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        Text("Your day", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text(summary?.spokenText ?: "No summary.", style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(12.dp))
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            summary?.let {
                items(it.tasks, key = { t -> t.id }) { t ->
                    Text("• ${t.title}  (${t.priority}/${t.status})")
                }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = onSpeak, modifier = Modifier.weight(1f)) { Text("Speak again") }
            Button(onClick = onDone, modifier = Modifier.weight(1f)) { Text("Done") }
        }
    }
}

@Composable
fun PairingScreen(state: UiState, onPair: (String, String) -> Unit) {
    var url by remember { mutableStateOf(state.backendUrl) }
    var code by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Pair this device", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("Backend URL") },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = code,
            onValueChange = { code = it },
            label = { Text("Registration code") },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = { onPair(url.trim(), code.trim()) },
            enabled = url.isNotBlank() && code.isNotBlank() && !state.busy,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Pair") }
    }
}

@Composable
fun SettingsScreen(state: UiState, onSave: (String) -> Unit, onDone: () -> Unit) {
    var url by remember { mutableStateOf(state.backendUrl) }
    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.Center) {
        Text("Settings", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("Backend URL") },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(20.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = { onSave(url.trim()) }, modifier = Modifier.weight(1f)) { Text("Save") }
            OutlinedButton(onClick = onDone, modifier = Modifier.weight(1f)) { Text("Back") }
        }
    }
}
