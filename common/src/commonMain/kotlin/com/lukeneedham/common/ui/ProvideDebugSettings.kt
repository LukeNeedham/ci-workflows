package com.lukeneedham.common.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import com.lukeneedham.common.DebugKit
import com.lukeneedham.common.debug.AnimationSpeed
import com.lukeneedham.common.debug.DebugSettings

/**
 * The debug settings as they apply to the UI right now: the saved values while debugging is
 * enabled, and the neutral defaults otherwise, so nothing saved while debugging can ever change a
 * release build. Read it through [LocalDebugSettings].
 *
 * Add a property here, with a neutral default, for every new debug setting that the UI needs to read.
 */
data class AppliedDebugSettings(
    /** How fast animations play. See [LocalAnimationSpeed]. */
    val animationSpeed: AnimationSpeed = AnimationSpeed.X1,
)

/**
 * Every debug setting that applies to the UI. Read a single value through its own local, such as
 * [LocalAnimationSpeed], or read this for all of them. It holds the neutral defaults until
 * [ProvideDebugSettings] is above the reader in the composition.
 */
val LocalDebugSettings = compositionLocalOf { AppliedDebugSettings() }

/**
 * The animation speed to apply. Read it where you build animation specs, and pass every duration
 * through [com.lukeneedham.common.debug.scale]:
 *
 * ```
 * tween(durationMillis = LocalAnimationSpeed.current.scale(300))
 * ```
 *
 * Provided by [ProvideDebugSettings], from [LocalDebugSettings].
 */
val LocalAnimationSpeed = compositionLocalOf { AnimationSpeed.X1 }

/**
 * The one place where this library provides composition locals to the app.
 *
 * **Every app must wrap its content in this once, near the root, even if it uses no debug setting
 * yet.** An app that does not need the animation speed today may need another setting tomorrow, and
 * wrapping from the start means a new setting reaches every screen without touching the app again.
 *
 * **Any composition local that this library offers to the app must be provided here**, and nowhere
 * else, so an app only ever has to make this one call. To add one:
 *  1. add the setting to [DebugSettings] (saved) and, if the UI reads it, to [AppliedDebugSettings]
 *     with a neutral default;
 *  2. declare its `CompositionLocal` next to [LocalAnimationSpeed];
 *  3. provide it in the `CompositionLocalProvider` below, from the applied settings;
 *  4. add its control to [DebugPage].
 *
 * Outside debugging ([com.lukeneedham.common.DebugKitConfig.enabled] is false) it provides the
 * defaults, so a setting saved while debugging can never change a release build.
 */
@Composable
fun ProvideDebugSettings(content: @Composable () -> Unit) {
    // Not enabled (including before DebugKit.init): do not even open the settings store.
    val applied = if (DebugKit.enabled) DebugKit.settings.applied(enabled = true) else AppliedDebugSettings()
    CompositionLocalProvider(
        LocalDebugSettings provides applied,
        LocalAnimationSpeed provides applied.animationSpeed,
        content = content,
    )
}

/** The settings the UI should use: the saved ones when [enabled], the defaults when not. */
internal fun DebugSettings.applied(enabled: Boolean): AppliedDebugSettings =
    if (enabled) AppliedDebugSettings(animationSpeed = animationSpeed) else AppliedDebugSettings()
