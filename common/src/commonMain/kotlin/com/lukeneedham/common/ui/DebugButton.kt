package com.lukeneedham.common.ui

import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.lukeneedham.common.DebugKit

/**
 * A button that opens the debug page. It shows nothing unless [com.lukeneedham.common.DebugKitConfig.enabled]
 * is set, so it can stay in the layout for release builds. Place it where you like, e.g. in a `Box`
 * with `Modifier.align(Alignment.BottomEnd)`.
 */
@Composable
fun DebugButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    if (!DebugKit.enabled) return
    ExtendedFloatingActionButton(onClick = onClick, modifier = modifier) { Text("Debug") }
}
