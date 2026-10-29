package com.lukeneedham.common.network

import com.lukeneedham.common.DebugKit
import okhttp3.Interceptor
import okhttp3.Response
import okio.Buffer

/**
 * Records every call of the OkHttp client it is added to into [DebugKit.network]:
 * `OkHttpClient.Builder().addInterceptor(NetworkLogInterceptor())`.
 *
 * Add it as an application interceptor. It does nothing unless debugging is enabled. Streaming
 * bodies (one-shot, duplex or event streams) and binary bodies are not read; they show as a note.
 */
class NetworkLogInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val log = DebugKit.network
        val request = chain.request()
        if (!log.isRecording) return chain.proceed(request)

        val requestBody = request.body?.let { body ->
            when {
                body.isOneShot() || body.isDuplex() -> "(streaming body, ${body.contentType() ?: "unknown type"})"
                !body.contentType().isText() -> "(binary body, ${body.contentType()}, ${body.contentLength()} bytes)"
                else -> Buffer().also { body.writeTo(it) }.readUtf8()
            }
        }
        val requestHeaders = request.headers.toList()
        val start = System.nanoTime()
        fun elapsedMs() = (System.nanoTime() - start) / 1_000_000

        val response = try {
            chain.proceed(request)
        } catch (e: Exception) {
            log.record(
                NetworkEntry(
                    id = 0, timeMs = System.currentTimeMillis(), method = request.method, url = request.url.toString(),
                    requestHeaders = requestHeaders, requestBody = requestBody,
                    durationMs = elapsedMs(), error = "${e::class.simpleName}: ${e.message}",
                ),
            )
            throw e
        }

        val responseBody = response.body?.let { body ->
            val type = body.contentType()
            when {
                !type.isText() -> "(binary body, $type, ${body.contentLength()} bytes)"
                else -> response.peekBody(PEEK_LIMIT).string()
            }
        }
        log.record(
            NetworkEntry(
                id = 0, timeMs = System.currentTimeMillis(), method = request.method, url = request.url.toString(),
                requestHeaders = requestHeaders, requestBody = requestBody,
                statusCode = response.code, statusMessage = response.message,
                responseHeaders = response.headers.toList(), responseBody = responseBody,
                durationMs = elapsedMs(),
            ),
        )
        return response
    }

    private fun okhttp3.MediaType?.isText(): Boolean {
        if (this == null) return true
        return type == "text" || subtype in TEXT_SUBTYPES || subtype.endsWith("+json") || subtype.endsWith("+xml")
    }

    private companion object {
        const val PEEK_LIMIT = 1_000_000L
        val TEXT_SUBTYPES = setOf("json", "xml", "html", "x-www-form-urlencoded", "javascript", "graphql")
    }
}
