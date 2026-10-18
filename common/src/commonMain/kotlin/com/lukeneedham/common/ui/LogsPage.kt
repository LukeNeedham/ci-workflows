package com.lukeneedham.common.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lukeneedham.common.logger.LogEntry
import com.lukeneedham.common.logger.LogLevel
import com.lukeneedham.common.logger.Logger

/** The logs saved to disk, newest first, with the text selectable so it can be copied. */
@Composable
fun LogsPage(onBack: () -> Unit, modifier: Modifier = Modifier) {
    var entries by remember { mutableStateOf(Logger.entries().asReversed()) }
    var minLevel by remember { mutableStateOf(LogLevel.Debug) }
    val shown = entries.filter { it.level >= minLevel }

    DebugScaffold(
        title = "Logs",
        onBack = onBack,
        modifier = modifier,
        actions = {
            DebugTextButton(text = "Refresh", onClick = { entries = Logger.entries().asReversed() })
            DebugTextButton(
                text = "Clear",
                onClick = {
                    Logger.clear()
                    entries = emptyList()
                },
            )
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                LogLevel.entries.forEach { level ->
                    DebugChip(label = level.name, selected = minLevel == level, onClick = { minLevel = level })
                }
            }
            if (shown.isEmpty()) {
                DebugText("No logs", modifier = Modifier.padding(16.dp))
            } else {
                SelectionContainer {
                    LazyColumn(
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        items(shown) { entry -> LogLine(entry) }
                    }
                }
            }
        }
    }
}

@Composable
private fun LogLine(entry: LogEntry) {
    DebugText(
        text = entry.format(),
        color = entry.level.color(),
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace,
    )
}

@Composable
private fun LogLevel.color(): Color {
    val theme = LocalDebugTheme.current
    return when (this) {
        LogLevel.Error -> theme.error
        LogLevel.Warning -> theme.warning
        else -> theme.onBackground
    }
}
