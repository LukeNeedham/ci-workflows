package com.lukeneedham.common.storage

/**
 * A [FileStore] that keeps everything in memory and loses it with the process.
 *
 * The fallback for when no real storage is available yet (see the Android default store), so logging
 * and debug settings keep working, without persisting, instead of throwing.
 */
internal class MemoryFileStore : FileStore {
    private val lock = createLock()
    private val files = mutableMapOf<String, String>()

    override fun read(name: String): String? = lock.withLock { files[name] }

    override fun write(name: String, text: String) = lock.withLock { files[name] = text }

    override fun append(name: String, text: String) = lock.withLock { files[name] = files[name].orEmpty() + text }

    override fun delete(name: String) = lock.withLock { files.remove(name); Unit }
}
