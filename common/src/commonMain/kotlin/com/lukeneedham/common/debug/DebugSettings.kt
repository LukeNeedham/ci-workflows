package com.lukeneedham.common.debug

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.lukeneedham.common.storage.FileStore
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json

/**
 * Settings that only make sense while debugging, saved to disk so they survive a restart.
 *
 * Read them in a composable and the UI follows changes. Whether they apply at all is up to the app:
 * see [com.lukeneedham.common.ui.ProvideAnimationSpeed], which ignores them unless debugging is enabled.
 */
class DebugSettings internal constructor(private val store: FileStore) {

    var animationSpeed by mutableStateOf(
        AnimationSpeed.entries.firstOrNull { it.name == readAll()[KEY_ANIMATION_SPEED] } ?: AnimationSpeed.X1,
    )
        private set

    fun selectAnimationSpeed(speed: AnimationSpeed) {
        animationSpeed = speed
        save(KEY_ANIMATION_SPEED, speed.name)
    }

    private fun save(key: String, value: String) {
        try {
            val updated = readAll() + (key to value)
            store.write(FILE, json.encodeToString(serializer, updated))
        } catch (_: Throwable) {
            // The setting still applies for this run; it just will not survive a restart.
        }
    }

    private fun readAll(): Map<String, String> = try {
        store.read(FILE)?.let { json.decodeFromString(serializer, it) } ?: emptyMap()
    } catch (_: Throwable) {
        emptyMap()
    }

    private companion object {
        const val FILE = "debug_settings.json"
        const val KEY_ANIMATION_SPEED = "animationSpeed"
        val json = Json { ignoreUnknownKeys = true }
        val serializer = MapSerializer(String.serializer(), String.serializer())
    }
}
