package com.lukeneedham.common.logger

import com.lukeneedham.common.formatTimestamp
import kotlinx.serialization.Serializable

/** Ordered from least to most severe, so levels can be compared. */
enum class LogLevel(val letter: Char) {
    Debug('D'),
    Info('I'),
    Warning('W'),
    Error('E'),
}

@Serializable
data class LogEntry(
    val timeMs: Long,
    val level: LogLevel,
    val tag: String? = null,
    val message: String,
    val stackTrace: String? = null,
) {
    /** One log line, followed by the stack trace if there is one. */
    fun format(): String = buildString {
        append(formatTimestamp(timeMs))
        append(' ')
        append(level.letter)
        if (tag != null) append('/').append(tag)
        append(": ").append(message)
        if (stackTrace != null) append('\n').append(stackTrace)
    }
}
