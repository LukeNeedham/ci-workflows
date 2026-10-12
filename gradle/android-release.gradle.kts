// Shared release setup for Android app modules. Apply it from the app's build.gradle.kts, after the
// plugins {} block:
//
//   apply(from = "https://raw.githubusercontent.com/LukeNeedham/ci-workflows/main/gradle/android-release.gradle.kts")
//
// and leave versionCode, versionName and the release signing config out of the app's own android {}
// block, as this script sets them. Setup guide: docs/setup.md
//
// Version. The git tags are the single source of truth: a release is made by tagging a commit
// MAJOR.MINOR.PATCH (no "v" prefix), which is what android_release.yml does.
//  - On a tagged commit the version name is the tag, e.g. 0.3.0.
//  - Anywhere else it is `git describe`, e.g. 0.3.0-5-gabc1234 (five commits after 0.3.0). With no
//    tag at all, or no tags fetched (as on the PR builds, which check out shallow), it is 0.0.0-dev.
//  - The version code is major*10000 + minor*100 + patch of the nearest tag (1 with none), so it
//    only rises with releases and an untagged build never outranks the next release.
//
// Signing. The release build type is signed with a key only when the environment provides one:
//   RELEASE_KEYSTORE_FILE, RELEASE_KEYSTORE_PASSWORD, RELEASE_KEY_ALIAS, RELEASE_KEY_PASSWORD
// (android_release.yml sets them from repo secrets). Without them the release APK stays unsigned,
// so a release can never be shipped with the wrong key.

import com.android.build.api.dsl.ApplicationExtension

fun git(vararg args: String): String? = try {
    val process = ProcessBuilder(listOf("git") + args)
        .directory(rootDir)
        .redirectError(ProcessBuilder.Redirect.DISCARD)
        .start()
    val output = process.inputStream.bufferedReader().readText().trim()
    output.takeIf { process.waitFor() == 0 && it.isNotEmpty() }
} catch (e: java.io.IOException) {
    null
}

val releaseTagGlob = "[0-9]*.[0-9]*.[0-9]*"
val nearestTag = git("describe", "--tags", "--abbrev=0", "--match", releaseTagGlob)
val gitVersionName = nearestTag
    ?.let { git("describe", "--tags", "--match", releaseTagGlob) }
    ?: "0.0.0-dev"
val gitVersionCode = nearestTag
    ?.let { Regex("""(\d+)\.(\d+)\.(\d+)""").matchEntire(it) }
    ?.destructured
    ?.let { (major, minor, patch) -> major.toInt() * 10000 + minor.toInt() * 100 + patch.toInt() }
    ?: 1

extensions.configure<ApplicationExtension> {
    defaultConfig {
        versionCode = gitVersionCode
        versionName = gitVersionName
    }
    signingConfigs {
        System.getenv("RELEASE_KEYSTORE_FILE")?.let { keystore ->
            create("release") {
                storeFile = file(keystore)
                storePassword = System.getenv("RELEASE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("RELEASE_KEY_ALIAS")
                keyPassword = System.getenv("RELEASE_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.findByName("release")
        }
    }
}
