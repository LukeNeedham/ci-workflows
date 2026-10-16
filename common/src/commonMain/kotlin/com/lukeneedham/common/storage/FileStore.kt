package com.lukeneedham.common.storage

import okio.FileSystem
import okio.Path
import okio.buffer
import okio.use

/**
 * Where the library keeps its files (logs, crashes, settings).
 *
 * Android and iOS back this with real files; the web has no file system, so it uses `localStorage`.
 * Implementations must tolerate being called from any thread, and callers swallow their failures:
 * persisting a log line must never be the reason an app breaks.
 */
internal interface FileStore {
    /** The whole file as text, or null if it does not exist. */
    fun read(name: String): String?

    /** Replaces the file, so a reader never sees half of the new content. */
    fun write(name: String, text: String)

    fun append(name: String, text: String)

    fun delete(name: String)
}

/** The store for this platform, in the app's private storage. */
internal expect fun createDefaultFileStore(): FileStore

/** A [FileStore] over okio, used for Android and iOS. Files live directly in [dir]. */
internal class OkioFileStore(
    private val fileSystem: FileSystem,
    private val dir: Path,
) : FileStore {

    private var dirCreated = false

    override fun read(name: String): String? {
        val path = dir / name
        if (!fileSystem.exists(path)) return null
        return fileSystem.read(path) { readUtf8() }
    }

    override fun write(name: String, text: String) {
        ensureDir()
        val target = dir / name
        val temp = dir / "$name.tmp"
        fileSystem.write(temp) { writeUtf8(text) }
        fileSystem.atomicMove(temp, target)
    }

    override fun append(name: String, text: String) {
        ensureDir()
        fileSystem.appendingSink(dir / name).buffer().use { it.writeUtf8(text) }
    }

    override fun delete(name: String) {
        fileSystem.delete(dir / name, mustExist = false)
    }

    private fun ensureDir() {
        if (dirCreated) return
        fileSystem.createDirectories(dir)
        dirCreated = true
    }
}
