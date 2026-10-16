package com.lukeneedham.common

import kotlin.time.Clock
import kotlin.time.ExperimentalTime

@OptIn(ExperimentalTime::class)
internal fun nowMillis(): Long = Clock.System.now().toEpochMilliseconds()

/** Formats [epochMs] as `yyyy-MM-dd HH:mm:ss.SSS` in UTC. No platform date API, so it is the same everywhere. */
internal fun formatTimestamp(epochMs: Long): String {
    val days = epochMs.floorDiv(MS_PER_DAY)
    val msOfDay = epochMs.mod(MS_PER_DAY)

    // Days since 1970-01-01 to a civil date (Howard Hinnant's algorithm).
    val z = days + 719_468
    val era = z.floorDiv(146_097L)
    val dayOfEra = z - era * 146_097
    val yearOfEra = (dayOfEra - dayOfEra / 1_460 + dayOfEra / 36_524 - dayOfEra / 146_096) / 365
    val dayOfYear = dayOfEra - (365 * yearOfEra + yearOfEra / 4 - yearOfEra / 100)
    val monthIndex = (5 * dayOfYear + 2) / 153
    val day = dayOfYear - (153 * monthIndex + 2) / 5 + 1
    val month = if (monthIndex < 10) monthIndex + 3 else monthIndex - 9
    val year = yearOfEra + era * 400 + if (month <= 2) 1 else 0

    val hour = msOfDay / 3_600_000
    val minute = msOfDay / 60_000 % 60
    val second = msOfDay / 1_000 % 60
    val milli = msOfDay % 1_000
    return "$year-${month.pad(2)}-${day.pad(2)} ${hour.pad(2)}:${minute.pad(2)}:${second.pad(2)}.${milli.pad(3)}"
}

private fun Long.pad(width: Int) = toString().padStart(width, '0')

private const val MS_PER_DAY = 86_400_000L
