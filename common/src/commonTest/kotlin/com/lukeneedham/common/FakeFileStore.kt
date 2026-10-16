package com.lukeneedham.common

import com.lukeneedham.common.storage.FileStore

internal class FakeFileStore : FileStore {
    val files = mutableMapOf<String, String>()
    override fun read(name: String) = files[name]
    override fun write(name: String, text: String) { files[name] = text }
    override fun append(name: String, text: String) { files[name] = files[name].orEmpty() + text }
    override fun delete(name: String) { files.remove(name) }
}
