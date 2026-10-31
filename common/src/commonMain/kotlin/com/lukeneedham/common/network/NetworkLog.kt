package com.lukeneedham.common.network

import com.lukeneedham.common.storage.createLock

/**
 * The network calls the app made since it started, newest first, kept in memory only (bodies and
 * headers can hold tokens and personal data, so they are never written to disk).
 *
 * Record into it from whichever HTTP client the app uses; the library ships an OkHttp interceptor
 * on Android ([NetworkLogInterceptor]). Nothing is recorded unless debugging is enabled.
 */
class NetworkLog internal constructor(
    private val maxEntries: Int = 100,
    private val maxBodyChars: Int = 100_000,
    private val enabled: () -> Boolean = { true },
) {
    private val lock = createLock()
    private var entries: List<NetworkEntry> = emptyList()
    private var nextId = 1L

    /** Whether calls are being recorded. Clients can skip reading bodies when it is false. */
    val isRecording: Boolean get() = enabled()

    /** Adds [entry] (its `id` is replaced) and returns the stored one. Bodies are cut to the size limit. */
    fun record(entry: NetworkEntry): NetworkEntry? {
        if (!enabled()) return null
        return lock.withLock {
            val stored = entry.copy(
                id = nextId++,
                requestBody = entry.requestBody?.truncated(),
                responseBody = entry.responseBody?.truncated(),
            )
            entries = (listOf(stored) + entries).take(maxEntries)
            stored
        }
    }

    /** Newest first. */
    fun entries(): List<NetworkEntry> = lock.withLock { entries }

    fun clear() = lock.withLock { entries = emptyList() }

    private fun String.truncated(): String =
        if (length <= maxBodyChars) this else take(maxBodyChars) + "\n… truncated (${length - maxBodyChars} more characters)"
}
