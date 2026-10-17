package com.lukeneedham.common.ui

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.lukeneedham.common.resources.Res
import com.lukeneedham.common.resources.ic_back
import org.jetbrains.compose.resources.painterResource

/** The top bar and back arrow shared by the debug pages. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun DebugScaffold(
    title: String,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    actions: @Composable RowScope.() -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(painterResource(Res.drawable.ic_back), contentDescription = "Back")
                    }
                },
                actions = actions,
            )
        },
        content = content,
    )
}
