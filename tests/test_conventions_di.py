import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import conventions.di as di
import conventions.naming as naming
import conventions.scan as scan
from conventions.core import lint

KOIN_MODULES = '''package com.example.app.di

import org.koin.dsl.module

object KoinModules {
    private val data = module {
        single { Repository(androidContext()) }
        singleOf(::Other)
    }

    val modules: List<Module> = listOf(data)
}
'''


def app(files):
    """A temporary app folder with [files] (path -> text), and the rules broken in it."""
    folder = tempfile.TemporaryDirectory()
    for name, text in files.items():
        path = Path(folder.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return folder


def rules(files):
    with app(files) as folder:
        return sorted({v.rule for v in lint(folder) if v.rule != "TOP-1"})


def messages(files):
    with app(files) as folder:
        return [f"{v.path}:{v.line} {v.rule} {v.message}" for v in lint(folder) if v.rule != "TOP-1"]


GOOD = {
    "app/src/main/java/com/example/app/di/KoinModules.kt": KOIN_MODULES,
    "app/src/main/java/com/example/app/App.kt":
        "package com.example.app\nimport org.koin.core.context.startKoin\n"
        "class App { fun f() { startKoin { modules(KoinModules.modules) } } }\n",
}


class SanitizeTest(unittest.TestCase):
    def test_comments_and_strings_are_blanked_and_lines_kept(self):
        text = 'val a = "AndroidViewModel" // AndroidViewModel\n/* AndroidViewModel\n */ val b = \'x\'\n'
        clean = scan.blank(text)
        self.assertNotIn("AndroidViewModel", clean)
        self.assertEqual(text.count("\n"), clean.count("\n"))
        self.assertEqual(len(text), len(clean))
        self.assertIn('"', clean)

    def test_raw_strings_and_escapes(self):
        clean = scan.blank('val a = """line "quoted"\nsecond"""\nval b = "a\\"b" val c = 1\n')
        self.assertIn("val c = 1", clean)
        self.assertNotIn("quoted", clean)


class AcronymTest(unittest.TestCase):
    def test_acronyms_in_capitals_are_found(self):
        for name in ("iOSSDKManager", "HTTPClient", "parseJSON", "UserDTO", "UIState", "userID", "newPP", "URLBuilder",
                     "UTF8Decoder", "apiURL", "XMLNode"):
            self.assertIsNotNone(naming.acronym_problem(name), name)

    def test_ordinary_camel_case_passes(self):
        for name in ("IosSdkManager", "HttpClient", "parseJson", "UserDto", "UiState", "userId", "newPausepoint", "UrlBuilder",
                     "Utf8Decoder", "API_URL", "MAX_COUNT", "x", "Id", "App", "Mp4File", "_unused"):
            self.assertIsNone(naming.acronym_problem(name), name)

    def test_a_one_letter_word_before_a_word_is_not_an_acronym(self):
        for name in ("parsesAUriAndABareId", "selectedXOffset", "startsAWord", "aRepoWithoutAMainBuildHasNone", "MPoem"):
            self.assertIsNone(naming.acronym_problem(name), name)

    def test_the_suggestion_writes_the_acronym_as_a_word(self):
        self.assertEqual("userId", naming.lower_acronyms("userID"))
        self.assertEqual("newPp", naming.lower_acronyms("newPP"))
        self.assertEqual("HttpClient", naming.lower_acronyms("HTTPClient"))
        self.assertEqual("parseJson", naming.lower_acronyms("parseJSON"))
        self.assertEqual("UiState", naming.lower_acronyms("UIState"))


class WiringTest(unittest.TestCase):
    def test_plain_bindings_are_wiring(self):
        for statement in (
            "single { Repository(get(), androidContext()) }",
            "single<Api> { KtorApi(client = get(), dao = get<AppDatabase>().dao()) }",
            "singleOf(::Repository)",
            "singleOf(::Impl) { bind<Interface>() }",
            "viewModelOf(::HomeViewModel)",
            "viewModel { (id: String, name: String?) -> DetailViewModel(id, name, get(), get(named(KoinQualifier.TOKEN))) }",
            "factory<CoroutineDispatcher>(KoinQualifier.Dispatcher.io) { Dispatchers.IO }",
            "single { HttpClientFactory.create() }",
            "single { PickViewModel(forced = params.getOrNull(), repository = get()) }",
            "single { Foo(\n    a = get(),\n    b = get(),\n)\n}",
            "single { Foo() } bind Bar::class",
        ):
            self.assertEqual([], di.wiring_problems(statement), statement)

    def test_each_kind_of_configuration_is_found(self):
        for statement in (
            'single { Foo("name") }',
            "single { Foo(30_000) }",
            "single { Foo(10L * 1024) }",
            "single { HttpClient(OkHttp) { install(Logging) } }",
            "single { OkHttpClient.Builder().cache(c).build() }",
            "single { Room.databaseBuilder(androidContext(), Db::class.java, name).build() }",
            "single { CoroutineScope(SupervisorJob() + Dispatchers.Main) }",
            "single { if (debug) A() else B() }",
            "single { File(androidContext().cacheDir, dir) }",
            "single { createDatabase(Factory(context).create()) }",
            "single { val x = 1; Foo(x) }",
        ):
            self.assertNotEqual([], di.wiring_problems(statement), statement)

    def test_something_that_is_not_a_binding_is_found(self):
        self.assertNotEqual([], di.wiring_problems("println(1)"))
        self.assertNotEqual([], di.wiring_problems("val x = 1"))


class CheckTest(unittest.TestCase):
    def test_a_good_app_passes(self):
        self.assertEqual([], rules(GOOD))

    def test_android_view_model_fails_even_in_tests(self):
        self.assertIn("VM-8", rules({**GOOD, "app/src/main/java/a/Vm.kt":
            "package a\nimport androidx.lifecycle.AndroidViewModel\nclass Vm(app: Application) : AndroidViewModel(app)\n"}))
        self.assertIn("VM-8", rules({**GOOD, "app/src/test/java/a/VmTest.kt": "class T : AndroidViewModel(x)\n"}))

    def test_the_word_in_a_comment_or_string_is_not_android_view_model(self):
        self.assertEqual([], rules({**GOOD, "app/src/main/java/a/Vm.kt":
            'package a\n/** Not an AndroidViewModel. */\n// AndroidViewModel is banned\nval s = "AndroidViewModel"\n'}))

    def test_an_app_without_koin_or_koin_modules_fails(self):
        self.assertEqual(["DI-1"], rules({"app/src/main/java/a/A.kt": "package a\nclass A\n"}))
        self.assertEqual(["DI-1"], rules({"app/src/main/java/a/A.kt": "package a\nimport org.koin.dsl.module\nclass A\n"}))

    def test_koin_modules_file_holds_only_the_object(self):
        path = "app/src/main/java/com/example/app/di/KoinModules.kt"
        for extra in ('const val TOKEN = "t"\n', "fun helper() = 1\n", "private val x = 1\n", "class Other\n",
                      "object KoinQualifier { const val A = \"a\" }\n"):
            self.assertIn("DI-2", rules({**GOOD, path: KOIN_MODULES + extra}), extra)

    def test_koin_modules_has_the_right_name_and_package(self):
        path = "app/src/main/java/com/example/app/di/KoinModules.kt"
        self.assertIn("DI-2", rules({**GOOD, path: KOIN_MODULES.replace("package com.example.app.di", "package com.example.app")}))
        self.assertIn("DI-2", rules({**GOOD, path: KOIN_MODULES.replace("object KoinModules", "object KoinModule")}))
        self.assertIn("DI-2", rules({**GOOD, "app/src/main/java/com/example/app/di/Other.kt":
            "package com.example.app.di\nobject KoinModules\n"}))

    def test_koin_qualifier_holds_only_the_object(self):
        qualifier = "app/src/main/java/com/example/app/di/KoinQualifier.kt"
        good = "package com.example.app.di\n\nobject KoinQualifier {\n    const val TOKEN = \"token\"\n}\n"
        self.assertEqual([], rules({**GOOD, qualifier: good}))
        self.assertIn("DI-2", rules({**GOOD, qualifier: good + "const val X = \"x\"\n"}))
        self.assertIn("DI-2", rules({**GOOD, qualifier: good.replace("KoinQualifier", "KoinQualifiers")}))

    def test_a_module_at_the_top_level_or_outside_di_fails(self):
        self.assertIn("DI-3", rules({**GOOD, "app/src/main/java/com/example/app/di/AppModule.kt":
            "package com.example.app.di\nval appModule = module {\n    singleOf(::A)\n}\n"}))
        self.assertIn("DI-3", rules({**GOOD, "app/src/main/java/com/example/app/Other.kt":
            "package com.example.app\nobject Other {\n    val m = module { singleOf(::A) }\n}\n"}))

    def test_a_feature_object_in_di_is_a_module_in_an_object(self):
        self.assertEqual([], rules({**GOOD, "app/src/main/java/com/example/app/di/AndroidModule.kt":
            "package com.example.app.di\nobject AndroidModule {\n    fun bindings(context: Context) = module {\n"
            "        single<Store> { DataStore(context) }\n    }\n}\n"}))

    def test_configuration_in_a_module_fails_with_the_line(self):
        path = "app/src/main/java/com/example/app/di/KoinModules.kt"
        bad = KOIN_MODULES.replace("singleOf(::Other)", 'single { Client("https://x") }')
        found = messages({**GOOD, path: bad})
        self.assertTrue(any("DI-4" in m and ":8 " in m for m in found), found)

    def test_a_string_qualifier_fails(self):
        self.assertIn("DI-5", rules({**GOOD, "app/src/main/java/com/example/app/di/Other.kt":
            'package com.example.app.di\nobject Other {\n    val m = module { single(named("x")) { A() } }\n}\n'}))
        self.assertEqual([], rules({**GOOD, "app/src/main/java/com/example/app/di/KoinQualifier.kt":
            'package com.example.app.di\nobject KoinQualifier {\n    fun name(n: String) = named("Dispatcher.$n")\n}\n'}))

    def test_starting_koin_without_koin_modules_fails(self):
        self.assertIn("DI-6", rules({**GOOD, "app/src/main/java/com/example/app/App.kt":
            "package com.example.app\nclass App { fun f() { startKoin { modules(appModule) } } }\n"}))

    def test_tests_are_not_held_to_the_module_rules(self):
        self.assertEqual([], rules({**GOOD, "app/src/test/java/a/KoinTest.kt":
            'package a\nval testModule = module { single { Foo("x") } }\n'}))

    def test_acronyms_are_found_in_declarations_files_and_parameters(self):
        for text in ("class UserDTO\n", "fun parseJSON() = 1\n", "val userID = 1\n", "fun f(userID: Int) = 1\n",
                     "fun Context.fetchURL() = 1\n", "typealias UIState = Int\n", "object HTTPClient\n"):
            self.assertIn("NAME-1", rules({**GOOD, "app/src/main/java/a/A.kt": "package a\n" + text}), text)
        self.assertIn("NAME-1", rules({**GOOD, "app/src/main/java/a/HTTPClient.kt": "package a\nclass Foo\n"}))

    def test_what_the_code_does_not_name_is_not_found(self):
        for text in ("val x = JSONArray()\n", "fun f() = userID\n", "override fun getURL() = 1\n", "val limit = MAX_COUNT\n",
                     'fun `parses a URL`() {}\n', "@Suppress(\"AcronymNaming\")\nval userID = 1\n", "// val userID = 1\n",
                     "fun f(dispatcher: CoroutineDispatcher) = Dispatchers.IO\n"):
            self.assertEqual([], rules({**GOOD, "app/src/main/java/a/A.kt": "package a\n" + text}), text)

    def test_build_folders_are_skipped(self):
        self.assertEqual([], rules({**GOOD, "app/build/generated/A.kt": "class UserDTO : AndroidViewModel(x)\n"}))


if __name__ == "__main__":
    unittest.main()


class TopLevelFunctionTest(unittest.TestCase):
    def found(self, text, name="app/src/main/java/com/example/app/Util.kt"):
        files = {**GOOD, name: "package com.example.app\n\n" + text}
        with app(files) as folder:
            return [v for v in lint(folder) if v.rule == "TOP-1"]

    def test_a_plain_or_private_top_level_function_fails(self):
        self.assertEqual(1, len(self.found("fun resolveIndex(days: List<Int>): Int = 0\n")))
        self.assertEqual(1, len(self.found("private fun helper() {}\n")))
        self.assertEqual(1, len(self.found("inline fun <reified T> make(): T = TODO()\n")))

    def test_extensions_and_composables_pass(self):
        self.assertEqual([], self.found("fun List<Int>.currentIndex(): Int = 0\n"))
        self.assertEqual([], self.found("fun <T : Comparable<T>> List<T>.second(): T = this[1]\n"))
        self.assertEqual([], self.found("private fun String?.orDash(): String = this ?: \"-\"\n"))
        self.assertEqual([], self.found("fun (() -> Unit).twice() { this(); this() }\n"))
        self.assertEqual([], self.found("@Composable\nfun Card() {}\n"))
        self.assertEqual([], self.found("@Preview\n@Composable\nprivate fun Preview() {}\n"))

    def test_expect_actual_external_and_main_pass(self):
        self.assertEqual([], self.found("expect fun readAppInfo(): String\n"))
        self.assertEqual([], self.found("actual fun readAppInfo(): String = \"\"\n"))
        self.assertEqual([], self.found("private external fun listenForErrors()\n"))
        self.assertEqual([], self.found("fun main() {}\n"))
        self.assertEqual(1, len(self.found("fun mainMenu() {}\n")))

    def test_members_properties_and_tests_are_not_top_level_functions(self):
        self.assertEqual([], self.found("object DayIndex {\n    fun resolve(days: List<Int>): Int = 0\n}\n"))
        self.assertEqual([], self.found("class Repo {\n    fun load() {}\n}\n"))
        self.assertEqual([], self.found("const val LIMIT = 3\nval names = listOf(\"a\")\n"))
        self.assertEqual([], self.found("fun helper() {}\n", "app/src/test/java/com/example/app/UtilTest.kt"))

    def test_lint_ignore_with_a_reason_silences_it(self):
        self.assertEqual([], self.found("// lint:ignore TOP-1: the platform looks this up by name\nfun entryPoint() {}\n"))
