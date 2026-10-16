package com.lukeneedham.common.storage

import com.lukeneedham.common.AppContext
import okio.FileSystem
import okio.Path.Companion.toPath
import java.util.concurrent.locks.ReentrantLock

internal actual fun createDefaultFileStore(): FileStore =
    OkioFileStore(FileSystem.SYSTEM, (AppContext.app.filesDir.absolutePath + "/common").toPath())

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
