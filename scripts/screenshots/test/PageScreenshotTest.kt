package com.lukeneedham.screenshots

import android.app.Application
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

// Plain test code of LukeNeedham/ci-workflows (scripts/screenshots, docs/screenshots.md), compiled into the app's unit tests
// by the Gradle init script for the screenshot run only: it is never copied into an app. The package of the app comes
// from the system property screenshots.package, which the init script sets to the namespace.
// Renders every @Preview of the app's screenshot package to build/screenshots/<Name>.png (of the app module), <Name> being
// the name of the composable without a trailing Screenshot. scripts/render_screenshots.py moves them to
// docs/screenshots/ once all of them are rendered.
@RunWith(ParameterizedRobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
// A plain Application: the app's own usually starts Koin, which fails the second time it is created
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi", application = Application::class)
class PageScreenshotTest(private val preview: ComposablePreview<AndroidPreviewInfo>) {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun render() {
        composeRule.setContent { preview() }
        // The tests run in the app module's directory
        composeRule.onRoot().captureRoboImage("build/screenshots/${preview.methodName.removeSuffix(SUFFIX)}.png")
    }

    companion object {
        private const val SUFFIX = "Screenshot"

        @JvmStatic
        @ParameterizedRobolectricTestRunner.Parameters(name = "{0}")
        fun previews(): List<Array<Any>> {
            val previews = AndroidComposablePreviewScanner()
                .scanPackageTrees("${System.getProperty("screenshots.package")}.screenshot")
                .includePrivatePreviews()
                .getPreviews()
                .toList()
            val names = previews.map { it.methodName.removeSuffix(SUFFIX) }
            require(names.distinct().size == names.size) {
                "Two screenshot composables have the same name, so one would overwrite the other's image: " +
                    names.groupBy { it }.filterValues { it.size > 1 }.keys
            }
            return previews.map { arrayOf(it) }
        }
    }
}
