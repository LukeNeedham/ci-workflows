package com.lukeneedham.common.crash

internal actual fun installCrashHook(
    onCrash: (thread: String?, type: String, message: String?, stackTrace: String) -> Unit,
) {
    val previous = Thread.getDefaultUncaughtExceptionHandler()
    Thread.setDefaultUncaughtExceptionHandler { thread, error ->
        try {
            onCrash(thread.name, error::class.java.name, error.message, error.stackTraceToString())
        } catch (_: Throwable) {
            // Never let recording hide the crash itself.
        }
        // Pass it on, so the app crashes exactly as it would have without us.
        previous?.uncaughtException(thread, error)
    }
}
