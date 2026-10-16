package com.lukeneedham.common

import com.lukeneedham.common.crash.CrashRepository
import com.lukeneedham.common.logger.LogLevel
import com.lukeneedham.common.logger.LogRepository
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CrashRepositoryTest {
    private val store = FakeFileStore()
    private var now = 1L
    private val logs = LogRepository(store, { now++ })
    private fun repo(max: Int = 20) = CrashRepository(store, { now++ }, logs, max)

    @Test fun recordsAndReadsBackNewestFirst() {
        val repo = repo()
        repo.record("main", "java.lang.IllegalStateException", "first", "trace 1")
        repo.record(null, "java.lang.Error", null, "trace 2")
        val crashes = repo.entries()
        assertEquals(listOf("trace 2", "trace 1"), crashes.map { it.stackTrace })
        assertEquals("main", crashes[1].thread)
        assertEquals("first", crashes[1].message)
    }

    @Test fun keepsOnlyTheMostRecent() {
        val repo = repo(max = 3)
        repeat(5) { repo.record(null, "T", null, "trace $it") }
        assertEquals(listOf("trace 4", "trace 3", "trace 2"), repo.entries().map { it.stackTrace })
    }

    @Test fun attachesTheLogsBeforeTheCrash() {
        logs.log(LogLevel.Info, "Net", "about to fail", null)
        repo().record(null, "T", null, "trace")
        assertTrue(repo().entries().single().recentLogs.contains("about to fail"))
    }

    @Test fun clearRemovesThem() {
        val repo = repo()
        repo.record(null, "T", null, "trace")
        repo.clear()
        assertEquals(emptyList(), repo.entries())
    }

    @Test fun ignoresACorruptFile() {
        store.write("crashes.jsonl", "garbage\n")
        val repo = repo()
        repo.record(null, "T", null, "trace")
        assertEquals(listOf("trace"), repo.entries().map { it.stackTrace })
    }
}
