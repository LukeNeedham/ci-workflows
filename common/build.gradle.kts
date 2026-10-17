import org.jetbrains.kotlin.gradle.ExperimentalWasmDsl
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidLibrary)
    alias(libs.plugins.kotlinSerialization)
    alias(libs.plugins.composeMultiplatform)
    alias(libs.plugins.composeCompiler)
    `maven-publish`
}

group = "com.lukeneedham"
// Set by the release workflow from the git tag; plain builds are a dev version.
version = providers.gradleProperty("libraryVersion").getOrElse("0.0.0-dev")

kotlin {
    androidTarget {
        compilerOptions { jvmTarget.set(JvmTarget.JVM_11) }
        publishLibraryVariants("release")
    }

    @OptIn(ExperimentalWasmDsl::class)
    wasmJs { browser() }

    iosX64()
    iosArm64()
    iosSimulatorArm64()

    sourceSets {
        commonMain.dependencies {
            implementation(libs.compose.runtime)
            implementation(libs.compose.foundation)
            implementation(libs.compose.material3)
            implementation(libs.compose.material.icons.core)
            implementation(libs.compose.ui)
            implementation(libs.kotlinx.serialization.json)
            implementation(libs.okio)
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.okio.fakefilesystem)
        }
    }
}

android {
    namespace = "com.lukeneedham.common"
    compileSdk = 36
    defaultConfig { minSdk = 23 }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

publishing {
    repositories {
        // A plain folder in Maven layout. The release workflow points -PstaticRepoDir at a checkout
        // of the gh-pages branch, which GitHub Pages then serves as a static Maven repository (see
        // docs/library.md). Apps add it as a `maven(url)` repository.
        maven {
            name = "staticRepo"
            url = providers.gradleProperty("staticRepoDir")
                .map { file(it).toURI() }
                .getOrElse(rootProject.layout.buildDirectory.dir("maven-repo").get().asFile.toURI())
        }
    }
    publications.withType<MavenPublication>().configureEach {
        pom {
            name.set("Common")
            description.set("Shared logger, crash handler and debug pages for my apps")
            url.set("https://github.com/LukeNeedham/ci-workflows")
            licenses {
                license {
                    name.set("Apache License 2.0")
                    url.set("https://www.apache.org/licenses/LICENSE-2.0.txt")
                }
            }
            scm { url.set("https://github.com/LukeNeedham/ci-workflows") }
        }
    }
}
