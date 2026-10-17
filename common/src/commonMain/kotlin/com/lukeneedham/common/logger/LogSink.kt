package com.lukeneedham.common.logger

/** The tag used when a log call gives none. */
internal const val DEFAULT_LOG_TAG = "App"

/**
 * Where [Logger] sends what it is given.
 *
 * Until [com.lukeneedham.common.DebugKit.init] runs this is [NoOpLogSink], which depends on nothing: no
 * application context, no `android.util.Log`, no files. That is what plain JVM unit tests get, since
 * they never start the app. `init` swaps in a [PersistentLogSink], so the real logger exists only in
 * an app that has started.
 */
internal interface LogSink {
    fun log(level: LogLevel, tag: String?, message: String, throwable: Throwable?)

    /** Everything kept, oldest first. */
    fun entries(): List<LogEntry>

    fun clear()
}

/** Does nothing, and needs nothing. The default. */
internal object NoOpLogSink : LogSink {
    override fun log(level: LogLevel, tag: String?, message: String, throwable: Throwable?) = Unit

    override fun entries(): List<LogEntry> = emptyList()

    override fun clear() = Unit
}

/** The real logger: the platform's own log (Logcat, the console) and a file on disk. */
internal class PersistentLogSink(private val repository: LogRepository) : LogSink {

    override fun log(level: LogLevel, tag: String?, message: String, throwable: Throwable?) {
        // Each part is guarded on its own, so one failing never stops the other, and logging never
        // throws into the caller.
        try {
            platformLog(level, tag ?: DEFAULT_LOG_TAG, message, throwable)
        } catch (_: Throwable) {
        }
        try {
            repository.log(level, tag, message, throwable)
        } catch (_: Throwable) {
        }
    }

    override fun entries(): List<LogEntry> = repository.entries()

    override fun clear() = repository.clear()
}
