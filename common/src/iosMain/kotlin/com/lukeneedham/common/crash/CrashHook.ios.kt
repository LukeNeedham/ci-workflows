package com.lukeneedham.common.crash

import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.staticCFunction
import platform.Foundation.NSException
import platform.Foundation.NSSetUncaughtExceptionHandler
import kotlin.experimental.ExperimentalNativeApi
import kotlin.native.setUnhandledExceptionHook
import kotlin.concurrent.Volatile

// staticCFunction cannot capture, so the callback lives in a top-level property.
@Volatile
private var crashCallback: ((String?, String, String?, String) -> Unit)? = null

@OptIn(ExperimentalNativeApi::class, ExperimentalForeignApi::class)
internal actual fun installCrashHook(
    onCrash: (thread: String?, type: String, message: String?, stackTrace: String) -> Unit,
) {
    crashCallback = onCrash

    // An unhandled Kotlin exception does not go through NSSetUncaughtExceptionHandler, only this hook.
    // After the hook returns, the runtime terminates the app as it normally would.
    setUnhandledExceptionHook { error ->
        try {
            onCrash(null, error::class.qualifiedName ?: "Throwable", error.message, error.stackTraceToString())
        } catch (_: Throwable) {
        }
    }

    // Objective-C exceptions raised across the interop boundary.
    NSSetUncaughtExceptionHandler(
        staticCFunction<NSException?, Unit> { exception ->
            val name = exception?.name ?: "NSException"
            val reason = exception?.reason
            val symbols = exception?.callStackSymbols?.joinToString("\n").orEmpty()
            try {
                crashCallback?.invoke(null, name, reason, "$name: $reason\n$symbols")
            } catch (_: Throwable) {
            }
        },
    )
}
