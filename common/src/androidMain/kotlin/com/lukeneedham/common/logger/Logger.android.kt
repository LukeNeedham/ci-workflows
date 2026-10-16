package com.lukeneedham.common.logger

import android.util.Log

internal actual fun platformLog(level: LogLevel, tag: String, message: String, throwable: Throwable?) {
    when (level) {
        LogLevel.Debug -> Log.d(tag, message, throwable)
        LogLevel.Info -> Log.i(tag, message, throwable)
        LogLevel.Warning -> Log.w(tag, message, throwable)
        LogLevel.Error -> Log.e(tag, message, throwable)
    }
}
