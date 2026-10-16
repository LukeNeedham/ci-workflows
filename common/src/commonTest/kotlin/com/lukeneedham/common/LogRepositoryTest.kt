package com.lukeneedham.common

import com.lukeneedham.common.logger.LogLevel
import com.lukeneedham.common.logger.LogRepository
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LogRepositoryTest {
    private val store = FakeFileStore()
    private var now = 1_000L
    private fun repo(maxChars: Int = 512_000, memorySize: Int = 200) =
        LogRepository(store, { now++ }, maxChars, memorySize)

    @Test fun readsBackWhatWasLogged() {
        val repo = repo()
        repo.log(LogLevel.Info, "Net", "hello\nsecond line", null)
        repo.log(LogLevel.Error, null, "boom", IllegalStateException("bad"))
        val entries = repo.entries()
        assertEquals(listOf("hello\nsecond line", "boom"), entries.map { it.message })
        assertEquals(listOf(LogLevel.Info, LogLevel.Error), entries.map { it.level })
        assertEquals("Net", entries[0].tag)
        assertTrue(entries[1].stackTrace!!.contains("IllegalStateException"))
    }

    @Test fun survivesANewInstance() {
        repo().log(LogLevel.Warning, null, "persisted", null)
        assertEquals(listOf("persisted"), repo().entries().map { it.message })
    }

    @Test fun skipsCorruptLines() {
        val repo = repo()
        repo.log(LogLevel.Info, null, "good", null)
        store.append("log.jsonl", "{not json\n")
        repo.log(LogLevel.Info, null, "also good", null)
        assertEquals(listOf("good", "also good"), repo.entries().map { it.message })
    }

    @Test fun dropsTheOldestHalfPastTheCap() {
        val repo = repo(maxChars = 2_000)
        repeat(100) { repo.log(LogLevel.Info, null, "message number $it", null) }
        val messages = repo.entries().map { it.message }
        assertTrue(messages.size < 100, "should have trimmed, had ${messages.size}")
        assertEquals("message number 99", messages.last())
        assertTrue(messages.first() != "message number 0")
    }

    @Test fun keepsOnlyTheNewestInMemory() {
        val repo = repo(memorySize = 3)
        repeat(5) { repo.log(LogLevel.Info, null, "m$it", null) }
        assertEquals(listOf("m2", "m3", "m4"), repo.recent(10).map { it.message })
        assertEquals(listOf("m3", "m4"), repo.recent(2).map { it.message })
    }

    @Test fun clearEmptiesDiskAndMemory() {
        val repo = repo()
        repo.log(LogLevel.Info, null, "x", null)
        repo.clear()
        assertEquals(emptyList(), repo.entries())
        assertEquals(emptyList(), repo.recent(10))
        repo.log(LogLevel.Info, null, "after", null)
        assertEquals(listOf("after"), repo.entries().map { it.message })
    }

    @Test fun formatsALine() {
        val repo = repo()
        now = 0
        repo.log(LogLevel.Warning, "Tag", "careful", null)
        assertEquals("1970-01-01 00:00:00.000 W/Tag: careful", repo.entries().single().format())
    }
}
