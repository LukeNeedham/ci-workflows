package com.lukeneedham.common.crash

import com.lukeneedham.common.logger.LogRepository
import com.lukeneedham.common.storage.FileStore
import com.lukeneedham.common.storage.createLock
import kotlinx.serialization.json.Json

/** Keeps the most recent [maxCrashes] crashes on disk, one JSON object per line. */
internal class CrashRepository(
    private val store: FileStore,
    private val clock: () -> Long,
    private val logs: LogRepository,
    private val maxCrashes: Int = 20,
) {
    private val lock = createLock()

    /** Called as the process is dying, so it does its disk write straight away, on the calling thread. */
    fun record(thread: String?, type: String, message: String?, stackTrace: String) {
        val entry = CrashEntry(
            timeMs = clock(),
            thread = thread,
            type = type,
            message = message,
            stackTrace = stackTrace,
            recentLogs = logs.recent(RECENT_LOG_COUNT).joinToString("\n") { it.format() },
        )
        lock.withLock {
            val kept = readAll().takeLast(maxCrashes - 1) + entry
            store.write(FILE, kept.joinToString(separator = "") { json.encodeToString(CrashEntry.serializer(), it) + "\n" })
        }
    }

    /** Newest first. */
    fun entries(): List<CrashEntry> = lock.withLock { readAll().asReversed() }

    fun clear() = lock.withLock {
        try {
            store.delete(FILE)
        } catch (_: Throwable) {
        }
    }

    private fun readAll(): List<CrashEntry> {
        val text = try {
            store.read(FILE)
        } catch (_: Throwable) {
            null
        }
        return text.orEmpty().lineSequence()
            .filter { it.isNotBlank() }
            .mapNotNull { line -> runCatching { json.decodeFromString<CrashEntry>(line) }.getOrNull() }
            .toList()
    }

    private companion object {
        const val FILE = "crashes.jsonl"
        const val RECENT_LOG_COUNT = 50
        val json = Json { ignoreUnknownKeys = true }
    }
}

/**
 * Installs the global handler for uncaught exceptions, once. The handler calls [onCrash] and then
 * lets the platform carry on crashing the app, exactly as it would have without it.
 */
internal expect fun installCrashHook(onCrash: (thread: String?, type: String, message: String?, stackTrace: String) -> Unit)
