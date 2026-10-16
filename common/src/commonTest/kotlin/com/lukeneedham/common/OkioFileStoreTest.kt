package com.lukeneedham.common

import com.lukeneedham.common.storage.OkioFileStore
import okio.Path.Companion.toPath
import okio.fakefilesystem.FakeFileSystem
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class OkioFileStoreTest {
    private val store = OkioFileStore(FakeFileSystem(), "/data/common".toPath())

    @Test fun missingFileReadsAsNull() = assertNull(store.read("a"))

    @Test fun appendCreatesThenExtends() {
        store.append("a", "one\n")
        store.append("a", "two\n")
        assertEquals("one\ntwo\n", store.read("a"))
    }

    @Test fun writeReplaces() {
        store.write("a", "old")
        store.write("a", "new")
        assertEquals("new", store.read("a"))
    }

    @Test fun deleteRemovesAndToleratesMissing() {
        store.write("a", "x")
        store.delete("a")
        store.delete("a")
        assertNull(store.read("a"))
    }

    @Test fun handlesUnicode() {
        store.write("a", "héllo 🐞")
        assertEquals("héllo 🐞", store.read("a"))
    }
}
