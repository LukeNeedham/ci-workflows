package com.lukeneedham.common

import com.lukeneedham.common.crash.CrashEntry
import com.lukeneedham.common.crash.CrashRepository
import com.lukeneedham.common.crash.installCrashHook
import com.lukeneedham.common.debug.DebugSettings
import com.lukeneedham.common.logger.LogLevel
import com.lukeneedham.common.logger.LogSink
import com.lukeneedham.common.logger.NoOpLogSink
import com.lukeneedham.common.logger.PersistentLogSink
import com.lukeneedham.common.logger.LogRepository
import com.lukeneedham.common.storage.createDefaultFileStore

class DebugKitConfig(
    /**
     * Whether the debug UI is on: the debug button, and the saved debug settings taking effect.
     * Pass whether this is a debug build. Logging and crash capture work either way.
     */
    val enabled: Boolean = false,
    /** Log calls below this level are dropped. */
    val minLogLevel: LogLevel = LogLevel.Debug,
    /** The log file is trimmed to its newest half once it passes this many characters. */
    val maxLogChars: Int = 512_000,
    /** How many crashes to keep. */
    val maxCrashes: Int = 20,
)

/**
 * Entry point: call [init] once, as early as you can, from `Application.onCreate` on Android or the
 * app's start-up on iOS and web.
 */
object DebugKit {

    var config: DebugKitConfig = DebugKitConfig()
        private set

    val enabled: Boolean get() = config.enabled

    private var initialized = false

    /**
     * Where [com.lukeneedham.common.logger.Logger] writes. A no-op until [init] swaps in the real
     * logger, so nothing logs, touches storage or needs an application context before the app starts.
     */
    internal var logSink: LogSink = NoOpLogSink
        private set

    /**
     * Applies [config], turns on the real logger and starts capturing crashes. A crash is written to
     * disk and then the platform carries on and crashes the app as normal. Safe to call more than once.
     *
     * Call it first thing in `Application.onCreate`: [com.lukeneedham.common.logger.Logger] drops
     * everything logged before it.
     */
    fun init(config: DebugKitConfig = DebugKitConfig()) {
        this.config = config
        if (initialized) return
        initialized = true
        logSink = PersistentLogSink(logs)
        installCrashHook { thread, type, message, stackTrace ->
            try {
                logs.log(LogLevel.Error, "Crash", "Uncaught $type: $message", null)
                crashes.record(thread, type, message, stackTrace)
            } catch (_: Throwable) {
                // Never let recording the crash hide the crash itself.
            }
        }
    }

    /** The crashes on disk, newest first. */
    fun crashes(): List<CrashEntry> = crashes.entries()

    fun clearCrashes() = crashes.clear()

    /** Debug-only settings, such as the animation speed. */
    val settings: DebugSettings by lazy { DebugSettings(fileStore) }

    private val fileStore by lazy { createDefaultFileStore() }

    internal val logs: LogRepository by lazy { LogRepository(fileStore, ::nowMillis, config.maxLogChars) }

    private val crashes: CrashRepository by lazy { CrashRepository(fileStore, ::nowMillis, logs, config.maxCrashes) }
}
