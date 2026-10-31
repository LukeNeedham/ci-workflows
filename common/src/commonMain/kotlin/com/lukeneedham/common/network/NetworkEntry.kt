package com.lukeneedham.common.network

/** One HTTP call the app made, as recorded by [NetworkLog]. */
data class NetworkEntry(
    val id: Long,
    val timeMs: Long,
    val method: String,
    val url: String,
    val requestHeaders: List<Pair<String, String>> = emptyList(),
    val requestBody: String? = null,
    /** The HTTP status code, or null if the call failed before a response arrived. */
    val statusCode: Int? = null,
    val statusMessage: String? = null,
    val responseHeaders: List<Pair<String, String>> = emptyList(),
    val responseBody: String? = null,
    val durationMs: Long = 0,
    /** Set when the call failed without a response (no connection, timeout, ...). */
    val error: String? = null,
) {
    val isSuccess: Boolean get() = statusCode != null && statusCode in 200..399
}
