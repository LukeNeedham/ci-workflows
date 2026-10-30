package com.lukeneedham.common.network

import io.ktor.client.HttpClientConfig
import io.ktor.client.engine.okhttp.OkHttpConfig
import okhttp3.OkHttpClient

/** Records every call of this OkHttp client into the network log: `OkHttpClient.Builder().logNetwork().build()`. */
fun OkHttpClient.Builder.logNetwork(): OkHttpClient.Builder = addInterceptor(NetworkLogInterceptor())

/**
 * Records every call of this Ktor client into the network log, for a client on the OkHttp engine:
 * `HttpClient(OkHttp) { logNetwork() }`. Calls the engine's `addInterceptor`, so it can sit next to an
 * `engine { }` block of your own.
 *
 * Needs `ktor-client-okhttp` in the app, which every app with that engine already has: the library
 * does not bring Ktor.
 */
fun HttpClientConfig<OkHttpConfig>.logNetwork() {
    engine { addInterceptor(NetworkLogInterceptor()) }
}
