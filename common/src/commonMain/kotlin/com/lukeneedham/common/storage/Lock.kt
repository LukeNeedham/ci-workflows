package com.lukeneedham.common.storage

internal interface Lock {
    fun <T> withLock(block: () -> T): T
}

/** A reentrant lock; a no-op on the single-threaded web. */
internal expect fun createLock(): Lock
