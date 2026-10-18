package com.lukeneedham.common.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.lukeneedham.common.resources.Res
import com.lukeneedham.common.resources.ic_back
import org.jetbrains.compose.resources.painterResource

/**
 * The top bar and back arrow shared by the debug pages. [content] gets the space under the bar as
 * padding, to be applied to whatever it lays out.
 */
@Composable
internal fun DebugScaffold(
    title: String,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    actions: @Composable RowScope.() -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    val theme = LocalDebugTheme.current
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(theme.background)
            .windowInsetsPadding(WindowInsets.safeDrawing),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().sizeIn(minHeight = 56.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
                    .clickable(role = Role.Button, onClick = onBack),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(Res.drawable.ic_back),
                    contentDescription = "Back",
                    colorFilter = ColorFilter.tint(theme.onBackground),
                )
            }
            DebugText(
                text = title,
                modifier = Modifier.weight(1f).padding(start = 8.dp),
                fontSize = 20.sp,
                fontWeight = FontWeight.Medium,
            )
            actions()
        }
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            content(PaddingValues())
        }
    }
}
