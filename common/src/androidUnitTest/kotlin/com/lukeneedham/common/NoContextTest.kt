package com.lukeneedham.common

import com.lukeneedham.common.logger.Logger
import com.lukeneedham.common.storage.createDefaultFileStore
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Plain JVM unit tests of an app run no content provider, so `CommonInitProvider` never sets the
 * application context, and `android.util.Log` is a stub. Logging must still not throw.
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

    @Test fun loggingDoesNotThrowAndIsReadBack() {
        Logger.clear()
        Logger.i("hello from a unit test")
        Logger.e("failed", IllegalStateException("boom"))
        val messages = Logger.entries().map { it.message }
        assertTrue("hello from a unit test" in messages)
        assertTrue("failed" in messages)
    }

    @Test fun initAndSettingsDoNotThrow() {
        DebugKit.init(DebugKitConfig(enabled = true))
        assertEquals(com.lukeneedham.common.debug.AnimationSpeed.X1, DebugKit.settings.animationSpeed)
    }
}
