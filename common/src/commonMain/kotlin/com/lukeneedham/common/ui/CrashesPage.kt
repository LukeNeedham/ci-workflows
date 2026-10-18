package com.lukeneedham.common.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lukeneedham.common.DebugKit
import com.lukeneedham.common.crash.CrashEntry
import com.lukeneedham.common.formatTimestamp

/** The crashes saved to disk, newest first. Tap one to see its stack trace and the logs before it. */
@Composable
fun CrashesPage(onBack: () -> Unit, modifier: Modifier = Modifier) {
    var crashes by remember { mutableStateOf(DebugKit.crashes()) }

    DebugScaffold(
        title = "Crashes",
        onBack = onBack,
        modifier = modifier,
        actions = {
            DebugTextButton(
                text = "Clear",
                onClick = {
                    DebugKit.clearCrashes()
                    crashes = emptyList()
                },
            )
        },
    ) { padding ->
        if (crashes.isEmpty()) {
            DebugText("No crashes", modifier = Modifier.padding(padding).padding(16.dp))
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(crashes) { crash -> CrashCard(crash) }
            }
        }
    }
}

@Composable
private fun CrashCard(crash: CrashEntry) {
    val theme = LocalDebugTheme.current
    var expanded by remember { mutableStateOf(false) }
    DebugCard(modifier = Modifier.fillMaxWidth(), onClick = { expanded = !expanded }) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            DebugText(formatTimestamp(crash.timeMs), color = theme.onSurface, fontSize = 12.sp)
            DebugText(crash.type, color = theme.error, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            crash.message?.let { DebugText(it, color = theme.onSurface) }
            if (expanded) {
                SelectionContainer {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        crash.thread?.let { Monospace("Thread: $it") }
                        Monospace(crash.stackTrace)
                        if (crash.recentLogs.isNotEmpty()) {
                            DebugText("Last logs", color = theme.onSurface, fontWeight = FontWeight.Medium)
                            Monospace(crash.recentLogs)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Monospace(text: String) {
    DebugText(text, color = LocalDebugTheme.current.onSurface, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
}
