package com.lukeneedham.common.storage

import okio.FileSystem
import okio.Path.Companion.toPath
import platform.Foundation.NSApplicationSupportDirectory
import platform.Foundation.NSRecursiveLock
import platform.Foundation.NSSearchPathForDirectoriesInDomains
import platform.Foundation.NSUserDomainMask

internal actual fun createDefaultFileStore(): FileStore {
    val appSupport = NSSearchPathForDirectoriesInDomains(
        directory = NSApplicationSupportDirectory,
        domainMask = NSUserDomainMask,
        expandTilde = true,
    ).first() as String
    return OkioFileStore(FileSystem.SYSTEM, "$appSupport/common".toPath())
}

internal actual fun createLock(): Lock = object : Lock {
    private val lock = NSRecursiveLock()

    override fun <T> withLock(block: () -> T): T {
        lock.lock()
        try {
            return block()
        } finally {
            lock.unlock()
        }
    }
}
