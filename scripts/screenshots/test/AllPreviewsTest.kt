package com.lukeneedham.screenshots

import android.app.Application
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import sergio.sastre.composable.preview.scanner.android.AndroidComposablePreviewScanner
import sergio.sastre.composable.preview.scanner.android.AndroidPreviewInfo
import sergio.sastre.composable.preview.scanner.core.preview.ComposablePreview

// Plain test code of LukeNeedham/ci-workflows (scripts/previews.py, docs/previews.md), compiled into the app's unit tests
// by the Gradle init script for the preview run only: it is never copied into an app. Renders EVERY @Preview of the app's
// package (private ones included) to build/previews/<class>.<function>.png of the app module, so that the PR can show the
// ones that changed. A preview that fails to render is listed in build/previews/failed.txt (the other previews still render); scripts/previews.py then fails the run.
@RunWith(ParameterizedRobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi", application = Application::class)
class AllPreviewsTest(private val name: String, private val preview: ComposablePreview<AndroidPreviewInfo>) {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun render() {
        try {
            composeRule.setContent { CompositionLocalProvider(LocalInspectionMode provides true) { preview() } }
            composeRule.onRoot().captureRoboImage("build/previews/$name.png")
        } catch (e: Throwable) {
            val dir = java.io.File("build/previews").apply { mkdirs() }
            java.io.File(dir, "failed.txt").appendText("$name: ${e::class.java.simpleName}: ${e.message?.lines()?.first()}\n")
        }
    }

    companion object {
        @JvmStatic
        @ParameterizedRobolectricTestRunner.Parameters(name = "{0}")
        fun previews(): List<Array<Any>> {
            val used = HashMap<String, Int>()
            return AndroidComposablePreviewScanner()
                .scanPackageTrees(System.getProperty("screenshots.package"))
                .includePrivatePreviews()
                .getPreviews()
                .map { preview ->
                    val base = "${preview.declaringClass}.${preview.methodName}".replace(Regex("[^A-Za-z0-9._-]"), "_")
                    // Two previews of one function (a parameter provider) get a number each
                    val count = used.merge(base, 1, Int::plus)!!
                    arrayOf<Any>(if (count == 1) base else "$base-$count", preview)
                }
        }
    }
}
