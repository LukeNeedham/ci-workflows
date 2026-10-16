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
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
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
            TextButton(
                onClick = {
                    DebugKit.clearCrashes()
                    crashes = emptyList()
                },
            ) { Text("Clear") }
        },
    ) { padding ->
        if (crashes.isEmpty()) {
            Text("No crashes", modifier = Modifier.padding(padding).padding(16.dp))
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
    var expanded by remember { mutableStateOf(false) }
    Card(modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded }) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(formatTimestamp(crash.timeMs), style = MaterialTheme.typography.labelMedium)
            Text(crash.type, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.error)
            crash.message?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            if (expanded) {
                SelectionContainer {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        crash.thread?.let { Monospace("Thread: $it") }
                        Monospace(crash.stackTrace)
                        if (crash.recentLogs.isNotEmpty()) {
                            Text("Last logs", style = MaterialTheme.typography.titleSmall)
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
    Text(text, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
}
