package com.lukeneedham.common.storage

import com.lukeneedham.common.AppContext
import okio.FileSystem
import okio.Path.Companion.toPath
import java.util.concurrent.locks.ReentrantLock

internal actual fun createDefaultFileStore(): FileStore = AndroidFileStore()

/**
 * Files in the app's private storage, once the application context is known.
 *
 * `CommonInitProvider` sets the context before `Application.onCreate`, so in an app this is always
 * the case. It is not in plain JVM unit tests, where no content provider runs: until it is, this
 * keeps things in memory rather than throwing, because logging must never be the reason an app or a
 * test fails.
 */
private class AndroidFileStore : FileStore {
    private val memory = MemoryFileStore()

    @Volatile
    private var disk: FileStore? = null

    private fun store(): FileStore {
        disk?.let { return it }
        if (!AppContext.isInitialized) return memory
        return OkioFileStore(FileSystem.SYSTEM, (AppContext.app.filesDir.absolutePath + "/common").toPath())
            .also { disk = it }
    }

    override fun read(name: String) = store().read(name)

    override fun write(name: String, text: String) = store().write(name, text)

    override fun append(name: String, text: String) = store().append(name, text)

    override fun delete(name: String) = store().delete(name)
}

internal actual fun createLock(): Lock = object : Lock {
    private val lock = ReentrantLock()

    override fun <T> withLock(block: () -> T): T {
        lock.lock()
        try {
            return block()
        } finally {
            lock.unlock()
        }
    }
}
