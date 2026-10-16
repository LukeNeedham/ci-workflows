package com.lukeneedham.common

import kotlin.test.Test
import kotlin.test.assertEquals

class FormatTimestampTest {
    @Test fun epoch() = assertEquals("1970-01-01 00:00:00.000", formatTimestamp(0))
    @Test fun knownInstant() = assertEquals("2023-11-14 22:13:20.123", formatTimestamp(1_700_000_000_123))
    @Test fun justBeforeEpoch() = assertEquals("1969-12-31 23:59:59.999", formatTimestamp(-1))
    @Test fun leapDay() = assertEquals("2024-02-29 00:00:00.000", formatTimestamp(1_709_164_800_000))
    @Test fun endOfYear() = assertEquals("2023-12-31 23:59:59.000", formatTimestamp(1_704_067_199_000))
}
