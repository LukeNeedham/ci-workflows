package com.lukeneedham.common.debug

import kotlin.math.roundToInt

/** How fast UI animations play; [multiplier] above 1 is faster, below 1 is slower. */
enum class AnimationSpeed(val multiplier: Float, val label: String) {
    X0_25(0.25f, "0.25x"),
    X0_5(0.5f, "0.5x"),
    X0_75(0.75f, "0.75x"),
    X1(1f, "1x"),
    X2(2f, "2x"),
}

/** [durationMs] with this speed applied: at 0.5x a 300ms animation takes 600ms. */
fun AnimationSpeed.scale(durationMs: Int): Int = (durationMs / multiplier).roundToInt()
