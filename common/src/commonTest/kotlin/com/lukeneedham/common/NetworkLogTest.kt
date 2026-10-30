package com.lukeneedham.common

import com.lukeneedham.common.network.NetworkEntry
import com.lukeneedham.common.network.NetworkLog
import com.lukeneedham.common.network.prettyIfJson
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NetworkLogTest {
    private fun entry(url: String, body: String? = null) =
        NetworkEntry(id = 0, timeMs = 1, method = "GET", url = url, responseBody = body, statusCode = 200)

    @Test fun keepsNewestFirstAndAssignsIds() {
        val log = NetworkLog()
        log.record(entry("a"))
        log.record(entry("b"))
        assertEquals(listOf("b", "a"), log.entries().map { it.url })
        assertEquals(listOf(2L, 1L), log.entries().map { it.id })
    }

    @Test fun dropsTheOldestPastTheLimit() {
        val log = NetworkLog(maxEntries = 2)
        listOf("a", "b", "c").forEach { log.record(entry(it)) }
        assertEquals(listOf("c", "b"), log.entries().map { it.url })
    }

    @Test fun truncatesLongBodies() {
        val log = NetworkLog(maxBodyChars = 10)
        log.record(entry("a", body = "x".repeat(50)))
        assertTrue(log.entries().single().responseBody!!.startsWith("xxxxxxxxxx\n… truncated (40"))
    }

    @Test fun recordsNothingWhenDisabled() {
        val log = NetworkLog(enabled = { false })
        assertNull(log.record(entry("a")))
        assertTrue(log.entries().isEmpty())
    }

    @Test fun clearEmptiesTheLog() {
        val log = NetworkLog()
        log.record(entry("a"))
        log.clear()
        assertTrue(log.entries().isEmpty())
    }

    @Test fun indentsJsonAndLeavesOtherTextAlone() {
        assertEquals("{\n    \"a\": 1\n}", """{"a":1}""".prettyIfJson())
        assertEquals("not json", "not json".prettyIfJson())
        assertEquals("{broken", "{broken".prettyIfJson())
    }
}
