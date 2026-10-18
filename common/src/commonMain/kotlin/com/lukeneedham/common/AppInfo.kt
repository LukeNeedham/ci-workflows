package com.lukeneedham.common

/**
 * Which app is running, shown at the top of the debug page so it reads the same in every consuming app.
 *
 * [version] is null where the platform has no version to read (the browser).
 */
internal class AppInfo(val id: String, val version: String?)

/** Null when it cannot be read, such as in plain JVM unit tests where no application context exists. */
internal expect fun readAppInfo(): AppInfo?
