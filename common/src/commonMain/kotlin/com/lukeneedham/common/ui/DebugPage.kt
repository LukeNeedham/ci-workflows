package com.lukeneedham.common.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.lukeneedham.common.DebugKit
import com.lukeneedham.common.debug.AnimationSpeed

/**
 * The debug hub: the debug settings, and links to the logs and crashes pages.
 *
 * It does not navigate itself: the app wires [onOpenLogs] and [onOpenCrashes] to its own navigation.
 * Put the app's own debug tools in [extraContent].
 */
@Composable
fun DebugPage(
    onBack: () -> Unit,
    onOpenLogs: () -> Unit,
    onOpenCrashes: () -> Unit,
    modifier: Modifier = Modifier,
    extraContent: @Composable ColumnScope.() -> Unit = {},
) {
    val settings = DebugKit.settings
    DebugScaffold(title = "Debug", onBack = onBack, modifier = modifier) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Animation speed", style = MaterialTheme.typography.titleMedium)
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                AnimationSpeed.entries.forEach { speed ->
                    FilterChip(
                        selected = settings.animationSpeed == speed,
                        onClick = { settings.selectAnimationSpeed(speed) },
                        label = { Text(speed.label) },
                    )
                }
            }
            HorizontalDivider()
            OutlinedButton(onClick = onOpenLogs, modifier = Modifier.fillMaxWidth()) { Text("Logs") }
            OutlinedButton(onClick = onOpenCrashes, modifier = Modifier.fillMaxWidth()) { Text("Crashes") }
            extraContent()
        }
    }
}
