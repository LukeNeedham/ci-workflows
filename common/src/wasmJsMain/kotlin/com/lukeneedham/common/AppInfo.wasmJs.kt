package com.lukeneedham.common

import kotlinx.browser.window

/** The browser has no package name or version, so the page's host stands in for the id. */
internal actual fun readAppInfo(): AppInfo? = AppInfo(window.location.host, null)
