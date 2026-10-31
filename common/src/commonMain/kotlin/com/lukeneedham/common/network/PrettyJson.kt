package com.lukeneedham.common.network

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement

private val prettyJson = Json { prettyPrint = true }

/** The text indented as JSON when it is JSON, otherwise unchanged. */
internal fun String.prettyIfJson(): String {
    val trimmed = trimStart()
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return this
    return try {
        prettyJson.encodeToString(JsonElement.serializer(), prettyJson.parseToJsonElement(this))
    } catch (_: Exception) {
        this
    }
}
