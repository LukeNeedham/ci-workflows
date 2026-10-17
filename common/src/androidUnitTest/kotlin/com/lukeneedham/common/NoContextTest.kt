package com.lukeneedham.common

import com.lukeneedham.common.debug.AnimationSpeed
import com.lukeneedham.common.logger.LogLevel
import com.lukeneedham.common.logger.LogRepository
import com.lukeneedham.common.logger.Logger
import com.lukeneedham.common.logger.NoOpLogSink
import com.lukeneedham.common.logger.PersistentLogSink
import com.lukeneedham.common.storage.createDefaultFileStore
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Plain JVM unit tests of an app run no content provider, so `CommonInitProvider` never sets the
 * application context, and `android.util.Log` is a stub. Logging must still not throw, and until the
 * app starts (`DebugKit.init`) it must not touch either.
 */
class NoContextTest {

    @Test fun defaultStoreWorksInMemoryWithoutAContext() {
        val store = createDefaultFileStore()
        assertNull(store.read("a.txt"))
        store.write("a.txt", "x")
        store.append("a.txt", "y")
        assertEquals("xy", store.read("a.txt"))
        store.delete("a.txt")
        assertNull(store.read("a.txt"))
    }

    @Test fun noOpSinkNeedsNothingAndKeepsNothing() {
        NoOpLogSink.log(LogLevel.Error, "tag", "message", IllegalStateException("boom"))
        assertTrue(NoOpLogSink.entries().isEmpty())
        NoOpLogSink.clear()
    }

    @Test fun persistentSinkKeepsEntriesEvenWhenThePlatformLogIsAStub() {
        val sink = PersistentLogSink(LogRepository(FakeFileStore(), { 1L }))
        sink.log(LogLevel.Info, null, "hello", null)
        sink.log(LogLevel.Error, "tag", "failed", IllegalStateException("boom"))
        assertEquals(listOf("hello", "failed"), sink.entries().map { it.message })
        sink.clear()
        assertTrue(sink.entries().isEmpty())
    }

    /**
     * One test, because [Logger] and [DebugKit] are global: this is the only place the app is
     * "started", so the order is fixed.
     */
    @Test fun loggerDoesNothingUntilTheAppStartsAndThenLogs() {
        // Before DebugKit.init: nothing throws, nothing is kept.
        Logger.i("before init")
        Logger.e("failed before init", IllegalStateException("boom"))
        assertTrue(Logger.entries().isEmpty())
        Logger.clear()

        DebugKit.init(DebugKitConfig(enabled = true))

        Logger.i("after init")
        Logger.e("failed after init", IllegalStateException("boom"))
        assertEquals(listOf("after init", "failed after init"), Logger.entries().map { it.message })
        assertEquals(AnimationSpeed.X1, DebugKit.settings.animationSpeed)
        Logger.clear()
        assertTrue(Logger.entries().isEmpty())
    }
}
