package com.lukeneedham.common.logger

import com.lukeneedham.common.DebugKit

/**
 * Logs to the platform's own log (Logcat, the console) and to a file on disk, so the logs can be
 * read back later from the Logs page, even after the app has been restarted or has crashed.
 *
 * Call [com.lukeneedham.common.DebugKit.init] first to configure it. It works without, with defaults.
 */
object Logger {

    fun d(message: String, tag: String? = null) = log(LogLevel.Debug, tag, message, null)

    fun i(message: String, tag: String? = null) = log(LogLevel.Info, tag, message, null)

    fun w(message: String, throwable: Throwable? = null, tag: String? = null) =
        log(LogLevel.Warning, tag, message, throwable)

    fun e(message: String, throwable: Throwable? = null, tag: String? = null) =
        log(LogLevel.Error, tag, message, throwable)

    /** Everything on disk, oldest first. */
    fun entries(): List<LogEntry> = DebugKit.logs.entries()

    fun clear() = DebugKit.logs.clear()

    private fun log(level: LogLevel, tag: String?, message: String, throwable: Throwable?) {
        if (level < DebugKit.config.minLogLevel) return
        // Logging must never throw into the caller, whatever the platform log or the storage does
        // (for example `android.util.Log` is not available in plain JVM unit tests).
        try {
            platformLog(level, tag ?: DEFAULT_TAG, message, throwable)
        } catch (_: Throwable) {
        }
        try {
            DebugKit.logs.log(level, tag, message, throwable)
        } catch (_: Throwable) {
        }
    }

    private const val DEFAULT_TAG = "App"
}

/** Writes to the platform's own log. */
internal expect fun platformLog(level: LogLevel, tag: String, message: String, throwable: Throwable?)
