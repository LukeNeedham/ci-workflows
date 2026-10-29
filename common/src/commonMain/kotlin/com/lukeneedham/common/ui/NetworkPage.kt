package com.lukeneedham.common.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lukeneedham.common.DebugKit
import com.lukeneedham.common.formatTimestamp
import com.lukeneedham.common.network.NetworkEntry
import com.lukeneedham.common.network.prettyIfJson

/**
 * The network calls the app made since it started, newest first (see [com.lukeneedham.common.network.NetworkLog]).
 * Each call is a card that expands to its request and response: headers and bodies. The text is
 * selectable, and "Copy" puts the whole call on the clipboard.
 */
@Composable
fun NetworkPage(onBack: () -> Unit, modifier: Modifier = Modifier) {
    var entries by remember { mutableStateOf(DebugKit.network.entries()) }

    DebugScaffold(
        title = "Network",
        onBack = onBack,
        modifier = modifier,
        actions = {
            DebugTextButton(text = "Refresh", onClick = { entries = DebugKit.network.entries() })
            DebugTextButton(
                text = "Clear",
                onClick = {
                    DebugKit.network.clear()
                    entries = emptyList()
                },
            )
        },
    ) { padding ->
        NetworkPageContent(entries, modifier = Modifier.padding(padding))
    }
}

@Composable
internal fun NetworkPageContent(entries: List<NetworkEntry>, modifier: Modifier = Modifier) {
    if (entries.isEmpty()) {
        DebugText("No network calls", modifier = modifier.padding(16.dp))
    } else {
        LazyColumn(
            modifier = modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(entries, key = { it.id }) { entry -> NetworkCard(entry) }
        }
    }
}

@Composable
private fun NetworkCard(entry: NetworkEntry) {
    val theme = LocalDebugTheme.current
    var expanded by remember { mutableStateOf(false) }
    val clipboard = LocalClipboardManager.current
    val statusColor = if (entry.statusCode == null || entry.statusCode >= 400) theme.error else theme.onSurface
    DebugCard(modifier = Modifier.fillMaxWidth(), onClick = { expanded = !expanded }) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                DebugText(
                    formatTimestamp(entry.timeMs),
                    color = theme.onSurface,
                    fontSize = 12.sp,
                    modifier = Modifier.weight(1f),
                )
                DebugTextButton(text = "Copy", onClick = { clipboard.setText(AnnotatedString(entry.asText())) })
                DebugText(if (expanded) "▲" else "▼", color = theme.onSurface, fontSize = 12.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                DebugText(entry.method, color = theme.onSurface, fontWeight = FontWeight.Bold)
                DebugText(
                    entry.statusCode?.toString() ?: "Failed",
                    color = statusColor,
                    fontWeight = FontWeight.Bold,
                )
                DebugText("${entry.durationMs} ms", color = theme.onSurface)
            }
            DebugText(
                entry.url,
                color = theme.onSurface,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
            )
            if (expanded) {
                SelectionContainer {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Section("Request", entry.requestHeaders, entry.requestBody)
                        if (entry.error != null) {
                            DebugText("Error", color = theme.error, fontWeight = FontWeight.Medium)
                            Monospace(entry.error)
                        } else {
                            val status = listOfNotNull(entry.statusCode, entry.statusMessage?.takeIf { it.isNotBlank() })
                            Section("Response ${status.joinToString(" ")}", entry.responseHeaders, entry.responseBody)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Section(title: String, headers: List<Pair<String, String>>, body: String?) {
    val theme = LocalDebugTheme.current
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        DebugText(title.trim(), color = theme.onSurface, fontWeight = FontWeight.Medium)
        DebugText("Headers", color = theme.onSurface, fontSize = 12.sp)
        if (headers.isEmpty()) Monospace("(none)") else Monospace(headers.joinToString("\n") { "${it.first}: ${it.second}" })
        DebugText("Body", color = theme.onSurface, fontSize = 12.sp)
        Monospace(if (body.isNullOrEmpty()) "(empty)" else body.prettyIfJson())
    }
}

@Composable
private fun Monospace(text: String) {
    DebugText(text, color = LocalDebugTheme.current.onSurface, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
}

private fun NetworkEntry.asText(): String = buildString {
    appendLine("$method $url")
    appendLine("Time: ${formatTimestamp(timeMs)}  Duration: $durationMs ms")
    appendLine()
    appendLine("Request headers:")
    requestHeaders.forEach { appendLine("${it.first}: ${it.second}") }
    appendLine("Request body:")
    appendLine(requestBody.orEmpty())
    appendLine()
    if (error != null) {
        appendLine("Error: $error")
    } else {
        appendLine("Response: $statusCode ${statusMessage.orEmpty()}")
        responseHeaders.forEach { appendLine("${it.first}: ${it.second}") }
        appendLine("Response body:")
        appendLine(responseBody.orEmpty())
    }
}
