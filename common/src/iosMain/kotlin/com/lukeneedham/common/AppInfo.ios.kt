package com.lukeneedham.common

import platform.Foundation.NSBundle

internal actual fun readAppInfo(): AppInfo? {
    val bundle = NSBundle.mainBundle
    val id = bundle.bundleIdentifier ?: return null
    val name = bundle.objectForInfoDictionaryKey("CFBundleShortVersionString") as? String
    val build = bundle.objectForInfoDictionaryKey("CFBundleVersion") as? String
    val version = when {
        name != null && build != null -> "$name ($build)"
        else -> name ?: build
    }
    return AppInfo(id, version)
}
