package com.lukeneedham.common.crash

import kotlinx.serialization.Serializable

@Serializable
data class CrashEntry(
    val timeMs: Long,
    /** The thread that crashed, where the platform says. */
    val thread: String? = null,
    /** The exception class. */
    val type: String,
    val message: String? = null,
    val stackTrace: String,
    /** The last log lines before the crash, oldest first. */
    val recentLogs: String = "",
)
