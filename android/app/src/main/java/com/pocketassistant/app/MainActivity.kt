package com.pocketassistant.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pocketassistant.app.ui.CaptureViewModel
import com.pocketassistant.app.ui.PocketAppScreen
import com.pocketassistant.app.ui.theme.PocketTheme

class MainActivity : ComponentActivity() {
    private var micGranted by mutableStateOf(false)

    private val requestMic =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            micGranted = granted
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        micGranted = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED
        if (!micGranted) requestMic.launch(Manifest.permission.RECORD_AUDIO)

        setContent {
            PocketTheme {
                val vm: CaptureViewModel = viewModel()
                PocketAppScreen(vm = vm, micGranted = micGranted, onRequestMic = {
                    requestMic.launch(Manifest.permission.RECORD_AUDIO)
                })
            }
        }
    }
}
