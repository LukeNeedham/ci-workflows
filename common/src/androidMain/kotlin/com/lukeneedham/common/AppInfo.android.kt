package com.lukeneedham.common

import android.os.Build

internal actual fun readAppInfo(): AppInfo? {
    if (!AppContext.isInitialized) return null
    val context = AppContext.app
    return try {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        // longVersionCode needs API 28; the library's minSdk is 23.
        @Suppress("DEPRECATION")
        val build = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) info.longVersionCode else info.versionCode.toLong()
        AppInfo(context.packageName, "${info.versionName} ($build)")
    } catch (_: Exception) {
        null
    }
}
