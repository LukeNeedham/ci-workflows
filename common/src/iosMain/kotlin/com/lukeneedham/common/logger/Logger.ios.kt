package com.lukeneedham.common.logger

internal actual fun platformLog(level: LogLevel, tag: String, message: String, throwable: Throwable?) {
    println("${level.letter}/$tag: $message")
    throwable?.printStackTrace()
}
