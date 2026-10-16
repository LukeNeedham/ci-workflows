@file:OptIn(kotlin.js.ExperimentalWasmJsInterop::class)

package com.lukeneedham.common.crash

@JsFun(
    """
    (onError) => {
        window.addEventListener('error', (e) => {
            const error = e.error;
            onError(
                error && error.name ? String(error.name) : 'Error',
                String(e.message),
                String(error && error.stack ? error.stack : e.message),
            );
        });
        window.addEventListener('unhandledrejection', (e) => {
            const reason = e.reason;
            onError(
                reason && reason.name ? String(reason.name) : 'UnhandledRejection',
                String(reason && reason.message ? reason.message : reason),
                String(reason && reason.stack ? reason.stack : reason),
            );
        });
    }
    """,
)
private external fun listenForErrors(onError: (JsString, JsString, JsString) -> Unit)

internal actual fun installCrashHook(
    onCrash: (thread: String?, type: String, message: String?, stackTrace: String) -> Unit,
) {
    // The listeners do not stop the event, so the browser still reports the error as it would have.
    listenForErrors { type, message, stack ->
        onCrash(null, type.toString(), message.toString(), stack.toString())
    }
}
