package com.lukeneedham.common.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lukeneedham.common.DebugKit
import com.lukeneedham.common.debug.AnimationSpeed
import com.lukeneedham.common.readAppInfo

/**
 * The library's debug page: the app's package and current version, the debug settings, and links to the logs, crashes and network pages. It shows only
 * the library's own things and has no slot for anything else.
 *
 * It does not navigate itself: the app wires [onOpenLogs] and [onOpenCrashes], and [onOpenNetwork] if the app has the network page (the button is hidden when it is null) to its own navigation.
 *
 * An app with debug tools of its own makes its own debug page for them, and gives that page a button
 * that opens this one. An app with none can open this page directly.
 */
@Composable
fun DebugPage(
    onBack: () -> Unit,
    onOpenLogs: () -> Unit,
    onOpenCrashes: () -> Unit,
    modifier: Modifier = Modifier,
    onOpenNetwork: (() -> Unit)? = null,
) {
    val settings = DebugKit.settings
    val appInfo = remember { readAppInfo() }
    DebugScaffold(title = "Debug", onBack = onBack, modifier = modifier) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            appInfo?.let {
                DebugText(it.id, fontSize = 16.sp, fontWeight = FontWeight.Medium)
                it.version?.let { version -> DebugText("Version $version") }
                DebugDivider()
            }
            DebugText("Animation speed", fontSize = 16.sp, fontWeight = FontWeight.Medium)
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                AnimationSpeed.entries.forEach { speed ->
                    DebugChip(
                        label = speed.label,
                        selected = settings.animationSpeed == speed,
                        onClick = { settings.selectAnimationSpeed(speed) },
                    )
                }
            }
            DebugDivider()
            DebugOutlinedButton(text = "Logs", onClick = onOpenLogs, modifier = Modifier.fillMaxWidth())
            DebugOutlinedButton(text = "Crashes", onClick = onOpenCrashes, modifier = Modifier.fillMaxWidth())
            onOpenNetwork?.let {
                DebugOutlinedButton(text = "Network", onClick = it, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}
