package com.lukeneedham.common.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.lukeneedham.common.DebugKit

/**
 * A button that opens the debug page. It shows nothing unless [com.lukeneedham.common.DebugKitConfig.enabled]
 * is set, so it can stay in the layout for release builds. Place it on the app's settings page.
 * It is drawn with the [DebugTheme] given to [ProvideDebugSettings].
 */
@Composable
fun DebugButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    if (!DebugKit.enabled) return
    val theme = LocalDebugTheme.current
    Box(
        modifier = modifier
            .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(theme.primary)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        DebugText("Debug", color = theme.onPrimary, fontWeight = FontWeight.Medium)
    }
}
