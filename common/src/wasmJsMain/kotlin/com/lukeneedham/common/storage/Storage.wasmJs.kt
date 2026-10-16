package com.lukeneedham.common.storage

import kotlinx.browser.localStorage

/** The browser has no file system, so each file is one `localStorage` entry. */
internal actual fun createDefaultFileStore(): FileStore = LocalStorageFileStore

internal actual fun createLock(): Lock = object : Lock {
    override fun <T> withLock(block: () -> T): T = block()
}

private object LocalStorageFileStore : FileStore {
    override fun read(name: String): String? = localStorage.getItem(key(name))

    override fun write(name: String, text: String) = localStorage.setItem(key(name), text)

    override fun append(name: String, text: String) =
        localStorage.setItem(key(name), localStorage.getItem(key(name)).orEmpty() + text)

    override fun delete(name: String) = localStorage.removeItem(key(name))

    private fun key(name: String) = "common:$name"
}
