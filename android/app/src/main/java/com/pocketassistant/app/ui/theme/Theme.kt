package com.pocketassistant.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColors = darkColorScheme(
    primary = Color(0xFF6FE3C2),
    onPrimary = Color(0xFF00382C),
    secondary = Color(0xFF7FD0FF),
    background = Color(0xFF101418),
    surface = Color(0xFF161B20),
    error = Color(0xFFFFB4AB),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF006B58),
    onPrimary = Color(0xFFFFFFFF),
    secondary = Color(0xFF00658F),
    background = Color(0xFFF7FBF8),
    surface = Color(0xFFFFFFFF),
    error = Color(0xFFBA1A1A),
)

@Composable
fun PocketTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
