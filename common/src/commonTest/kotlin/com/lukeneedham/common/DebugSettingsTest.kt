package com.lukeneedham.common

import com.lukeneedham.common.debug.AnimationSpeed
import com.lukeneedham.common.debug.DebugSettings
import com.lukeneedham.common.debug.scale
import kotlin.test.Test
import kotlin.test.assertEquals

class DebugSettingsTest {
    private val store = FakeFileStore()

    @Test fun defaultsToNormalSpeed() = assertEquals(AnimationSpeed.X1, DebugSettings(store).animationSpeed)

    @Test fun savedSpeedSurvivesARestart() {
        DebugSettings(store).selectAnimationSpeed(AnimationSpeed.X0_5)
        assertEquals(AnimationSpeed.X0_5, DebugSettings(store).animationSpeed)
    }

    @Test fun latestChoiceWins() {
        val settings = DebugSettings(store)
        settings.selectAnimationSpeed(AnimationSpeed.X2)
        settings.selectAnimationSpeed(AnimationSpeed.X0_25)
        assertEquals(AnimationSpeed.X0_25, settings.animationSpeed)
        assertEquals(AnimationSpeed.X0_25, DebugSettings(store).animationSpeed)
    }

    @Test fun unknownOrCorruptSavedValueFallsBack() {
        store.write("debug_settings.json", """{"animationSpeed":"X99"}""")
        assertEquals(AnimationSpeed.X1, DebugSettings(store).animationSpeed)
        store.write("debug_settings.json", "garbage")
        assertEquals(AnimationSpeed.X1, DebugSettings(store).animationSpeed)
    }

    @Test fun scalesDurations() {
        assertEquals(300, AnimationSpeed.X1.scale(300))
        assertEquals(600, AnimationSpeed.X0_5.scale(300))
        assertEquals(1200, AnimationSpeed.X0_25.scale(300))
        assertEquals(150, AnimationSpeed.X2.scale(300))
    }
}
