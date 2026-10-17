package com.lukeneedham.common.logger

import com.lukeneedham.common.DebugKit

/**
 * Logs to the platform's own log (Logcat, the console) and to a file on disk, so the logs can be
 * read back later from the Logs page, even after the app has been restarted or has crashed.
 *
 * **Does nothing until [com.lukeneedham.common.DebugKit.init] has run**, so call that first thing in
 * `Application.onCreate`. That keeps it safe anywhere the app has not started, such as plain JVM unit
 * tests, where there is no application context and `android.util.Log` is a stub: calls there are
 * silently dropped, and [entries] is empty.
 */
object Logger {

    fun d(message: String, tag: String? = null) = log(LogLevel.Debug, tag, message, null)

    fun i(message: String, tag: String? = null) = log(LogLevel.Info, tag, message, null)

    fun w(message: String, throwable: Throwable? = null, tag: String? = null) =
        log(LogLevel.Warning, tag, message, throwable)

    fun e(message: String, throwable: Throwable? = null, tag: String? = null) =
        log(LogLevel.Error, tag, message, throwable)

    /** Everything on disk, oldest first. Empty until [com.lukeneedham.common.DebugKit.init] has run. */
    fun entries(): List<LogEntry> = DebugKit.logSink.entries()

    fun clear() = DebugKit.logSink.clear()

    private fun log(level: LogLevel, tag: String?, message: String, throwable: Throwable?) {
        if (level < DebugKit.config.minLogLevel) return
        // Logging must never throw into the caller.
        try {
            DebugKit.logSink.log(level, tag, message, throwable)
        } catch (_: Throwable) {
        }
    }
}

/** Writes to the platform's own log. */
internal expect fun platformLog(level: LogLevel, tag: String, message: String, throwable: Throwable?)
