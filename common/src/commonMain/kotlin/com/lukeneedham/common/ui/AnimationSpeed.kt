package com.lukeneedham.common.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import com.lukeneedham.common.DebugKit
import com.lukeneedham.common.debug.AnimationSpeed

/**
 * The animation speed to apply. Read it where you build animation specs, and pass every duration
 * through [com.lukeneedham.common.debug.scale]:
 *
 * ```
 * tween(durationMillis = LocalAnimationSpeed.current.scale(300))
 * ```
 */
val LocalAnimationSpeed = compositionLocalOf { AnimationSpeed.X1 }

/**
 * Provides [LocalAnimationSpeed] from the saved debug setting to [content]. Wrap the app's content
 * in it once, near the root. Outside debugging it always provides 1x, so a speed saved while
 * debugging can never slow down a release build.
 */
@Composable
fun ProvideAnimationSpeed(content: @Composable () -> Unit) {
    val speed = if (DebugKit.enabled) DebugKit.settings.animationSpeed else AnimationSpeed.X1
    CompositionLocalProvider(LocalAnimationSpeed provides speed, content = content)
}
