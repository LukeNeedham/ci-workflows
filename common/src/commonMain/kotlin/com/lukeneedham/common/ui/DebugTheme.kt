package com.lukeneedham.common.ui

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily

/**
 * What the library's pages look like. The app passes its own colours and typeface to
 * [ProvideDebugSettings], so the pages match the app without the library depending on any theme
 * system (the library does not use Material, and reads no app theme).
 *
 * Every parameter has a default, so an app that passes nothing gets a plain light theme. Prefer
 * passing the app's own values so the pages match.
 */
@Immutable
data class DebugTheme(
    /** Behind everything. */
    val background: Color = Color(0xFFFFFFFF),
    /** Text and icons on [background]. */
    val onBackground: Color = Color(0xFF1B1B1F),
    /** Cards and unselected chips, drawn on [background]. */
    val surface: Color = Color(0xFFEEEEF3),
    /** Text on [surface]. */
    val onSurface: Color = Color(0xFF1B1B1F),
    /** Selected chips and the debug button. */
    val primary: Color = Color(0xFF3F51B5),
    /** Text on [primary]. */
    val onPrimary: Color = Color(0xFFFFFFFF),
    /** Dividers and outlines. */
    val outline: Color = Color(0xFF8A8A94),
    /** Errors: crash types and error log lines. */
    val error: Color = Color(0xFFB3261E),
    /** Warning log lines. */
    val warning: Color = Color(0xFF8D6E00),
    /** Every piece of text on the pages. */
    val fontFamily: FontFamily = FontFamily.Default,
)

/**
 * The theme of the library's pages. Provided by [ProvideDebugSettings]; holds the default theme
 * until that is above the reader in the composition.
 */
val LocalDebugTheme = compositionLocalOf { DebugTheme() }
