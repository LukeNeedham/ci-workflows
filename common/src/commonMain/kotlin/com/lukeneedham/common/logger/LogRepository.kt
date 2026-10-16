package com.lukeneedham.common.logger

import com.lukeneedham.common.storage.FileStore
import com.lukeneedham.common.storage.createLock
import kotlinx.serialization.json.Json

/**
 * Keeps log entries on disk, one JSON object per line, so they survive the process dying.
 *
 * The file is capped: once it passes [maxChars] the oldest half is dropped. The newest [memorySize]
 * entries are also held in memory, so the crash handler can attach them without reading the disk.
 */
internal class LogRepository(
    private val store: FileStore,
    private val clock: () -> Long,
    private val maxChars: Int = 512_000,
    private val memorySize: Int = 200,
) {
    private val lock = createLock()
    private val recentEntries = ArrayDeque<LogEntry>()
    private var fileChars = -1

    fun log(level: LogLevel, tag: String?, message: String, throwable: Throwable?) {
        val entry = LogEntry(clock(), level, tag, message, throwable?.stackTraceToString())
        lock.withLock {
            recentEntries.addLast(entry)
            if (recentEntries.size > memorySize) recentEntries.removeFirst()
            try {
                persist(entry)
            } catch (_: Throwable) {
                // Logging must never throw into the caller.
            }
        }
    }

    /** Everything on disk, oldest first. Lines that cannot be read are skipped. */
    fun entries(): List<LogEntry> = lock.withLock {
        val text = try {
            store.read(FILE)
        } catch (_: Throwable) {
            null
        }
        text.orEmpty().lineSequence()
            .filter { it.isNotBlank() }
            .mapNotNull { line -> runCatching { json.decodeFromString<LogEntry>(line) }.getOrNull() }
            .toList()
    }

    /** The last [count] entries logged by this process, oldest first. */
    fun recent(count: Int): List<LogEntry> = lock.withLock { recentEntries.toList().takeLast(count) }

    fun clear() = lock.withLock {
        recentEntries.clear()
        fileChars = 0
        try {
            store.delete(FILE)
        } catch (_: Throwable) {
        }
    }

    private fun persist(entry: LogEntry) {
        val line = json.encodeToString(LogEntry.serializer(), entry) + "\n"
        if (fileChars < 0) fileChars = store.read(FILE)?.length ?: 0
        store.append(FILE, line)
        fileChars += line.length
        if (fileChars > maxChars) trim()
    }

    private fun trim() {
        val lines = store.read(FILE).orEmpty().lines().filter { it.isNotEmpty() }
        val kept = lines.drop(lines.size / 2).joinToString(separator = "") { it + "\n" }
        store.write(FILE, kept)
        fileChars = kept.length
    }

    private companion object {
        const val FILE = "log.jsonl"
        val json = Json { ignoreUnknownKeys = true }
    }
}
