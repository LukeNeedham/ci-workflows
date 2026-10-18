package com.lukeneedham.common.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// The building blocks of the debug pages. They read only LocalDebugTheme, never a Material theme.

/** The smallest size of anything clickable. */
private val MinTouchTarget = 48.dp

/** Text in the theme's font. [fontFamily] overrides it, for monospace. */
@Composable
internal fun DebugText(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = LocalDebugTheme.current.onBackground,
    fontSize: TextUnit = 14.sp,
    fontWeight: FontWeight? = null,
    fontFamily: FontFamily? = null,
) {
    BasicText(
        text = text,
        modifier = modifier,
        style = TextStyle(
            color = color,
            fontSize = fontSize,
            lineHeight = fontSize * 1.4f,
            fontWeight = fontWeight,
            fontFamily = fontFamily ?: LocalDebugTheme.current.fontFamily,
        ),
    )
}

/** A clickable text, in the primary colour. */
@Composable
internal fun DebugTextButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .sizeIn(minWidth = MinTouchTarget, minHeight = MinTouchTarget)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        DebugText(text, color = LocalDebugTheme.current.primary, fontWeight = FontWeight.Medium)
    }
}

/** A full-width outlined button. */
@Composable
internal fun DebugOutlinedButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val theme = LocalDebugTheme.current
    val shape = RoundedCornerShape(20.dp)
    Box(
        modifier = modifier
            .sizeIn(minWidth = MinTouchTarget, minHeight = MinTouchTarget)
            .clip(shape)
            .border(BorderStroke(1.dp, theme.outline), shape)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 24.dp),
        contentAlignment = Alignment.Center,
    ) {
        DebugText(text, color = theme.primary, fontWeight = FontWeight.Medium)
    }
}

/** A chip that is either selected or not. */
@Composable
internal fun DebugChip(label: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val theme = LocalDebugTheme.current
    val shape = RoundedCornerShape(8.dp)
    Box(
        modifier = modifier
            .sizeIn(minWidth = MinTouchTarget, minHeight = MinTouchTarget)
            .padding(vertical = 4.dp)
            .clip(shape)
            .background(if (selected) theme.primary else theme.surface)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        DebugText(label, color = if (selected) theme.onPrimary else theme.onSurface)
    }
}

/** A raised block of content. */
@Composable
internal fun DebugCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val theme = LocalDebugTheme.current
    val shape = RoundedCornerShape(12.dp)
    Column(
        modifier = modifier
            .clip(shape)
            .background(theme.surface)
            .let { if (onClick != null) it.clickable(onClick = onClick) else it },
    ) { content() }
}

@Composable
internal fun DebugDivider(modifier: Modifier = Modifier) {
    Box(modifier = modifier.fillMaxWidth().height(1.dp).background(LocalDebugTheme.current.outline))
}
