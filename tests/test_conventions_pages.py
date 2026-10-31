import io
import os
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _paths  # noqa: F401
import conventions.core as lc
import conventions.scan as k

UI = "app/src/main/kotlin/com/x/ui/"

CLEAN = {
    "HomePage.kt": '''
        package com.x.ui

        import androidx.compose.runtime.Composable
        import org.koin.androidx.compose.koinViewModel

        /** The page. */
        @Composable
        fun HomePage(onOpen: () -> Unit) {
            val viewModel = koinViewModel<HomeViewModel>()
            val state by viewModel.uiState.collectAsStateWithLifecycle()
            HomePageContent(state = state, onRefresh = viewModel::refresh, onOpen = onOpen)
        }
    ''',
    "HomePageContent.kt": '''
        package com.x.ui

        import androidx.compose.runtime.Composable
        import androidx.compose.ui.tooling.preview.Preview

        @Composable
        internal fun HomePageContent(state: HomeUiState, onRefresh: () -> Unit, onOpen: () -> Unit) {
            Text("hello ${state.title} \\"quoted\\" // not a comment")
            Text(state.title)
        }

        @Preview
        @Composable
        private fun Preview() {
            AppTheme { HomePageContent(state = HomeUiState("a"), onRefresh = {}, onOpen = {}) }
        }

        @Preview
        @Composable
        private fun PreviewEmpty() {
            AppTheme { HomePageContent(state = HomeUiState(""), onRefresh = {}, onOpen = {}) }
        }
    ''',
    "HomeViewModel.kt": '''
        package com.x.ui

        import androidx.lifecycle.ViewModel

        class HomeViewModel(private val repository: HomeRepository) : ViewModel() {
            val uiState: StateFlow<HomeUiState> = MutableStateFlow(HomeUiState("x"))
            private val events = Channel<String>(Channel.BUFFERED)
            fun refresh() {}
        }
    ''',
    "HomeUiState.kt": '''
        package com.x.ui

        data class HomeUiState(val title: String, val items: List<String> = emptyList())
    ''',
    "HomeCard.kt": '''
        package com.x.ui

        @Composable
        internal fun HomeCard(title: String) {
            Text(title)
        }

        @Preview
        @Composable
        private fun Preview() {
            AppTheme { HomeCard("a") }
        }
    ''',
}


def lint_app(extra=None, remove=(), outside=None):
    """The violations of a temporary app: CLEAN with [extra] files added or replaced (None removes), and [outside]
    files given by their path from the app root."""
    files = {UI + name: text for name, text in CLEAN.items() if name not in remove}
    for name, text in (extra or {}).items():
        files[UI + name] = text
    files.update(outside or {})
    with tempfile.TemporaryDirectory() as tmp:
        for path, text in files.items():
            if text is None:
                continue
            target = Path(tmp) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(text).lstrip("\n"))
        return [v for v in lc.lint(tmp) if not v.rule.startswith("DI-")]  # the Koin rules have tests of their own


def rules(violations):
    return sorted({v.rule for v in violations})


def assert_rule(test, violations, rule, text=None):
    found = [v for v in violations if v.rule == rule]
    test.assertTrue(found, f"{rule} not reported; got {[(v.rule, v.path, v.line, v.message) for v in violations]}")
    if text:
        test.assertTrue(any(text in v.message for v in found), [v.message for v in found])


class ScannerTest(unittest.TestCase):
    def test_comments_and_strings_are_blanked_with_every_offset_kept(self):
        src = 'val a = "x // y" // c\n/* b /* nested */ still */ val c = """r "q" \n s""" + \'\\n\'\n'
        clean = k.blank(src)
        self.assertEqual(len(clean), len(src))
        self.assertEqual(clean.count("\n"), src.count("\n"))
        for hidden in ("x // y", "// c", "nested", "still", 'r "q"', "\\n"):
            self.assertNotIn(hidden, clean)
        self.assertIn("val c", clean)

    def test_a_string_template_with_strings_inside_ends_where_it_should(self):
        clean = k.blank('val s = "a ${f("}")} b"\nval t = 1\n')
        self.assertIn("val t = 1", clean)
        self.assertNotIn("}", clean.split("\n")[0])

    def test_top_level_declarations_with_their_modifiers_and_annotations(self):
        src = textwrap.dedent('''
            package a.b

            @Composable
            @Preview(name = "x")
            private fun Preview() { inner() }

            internal data class HomeUiState(val a: Int)

            abstract class Base<T : Any>(val x: Int) : ViewModel(), Other {
                fun nested() {}
            }

            fun interface Handler { fun go() }
            val top = 1
        ''')
        _, decls = k.parse(src)
        self.assertEqual([d.name for d in decls], ["Preview", "HomeUiState", "Base", "Handler", "top"])
        preview, state, base, handler, _top = decls
        self.assertEqual((preview.kind, preview.mods, preview.annotations), ("fun", {"private"}, ["Composable", "Preview"]))
        self.assertTrue(preview.is_preview and preview.is_composable and preview.is_private)
        self.assertEqual((state.kind, state.mods, state.params.strip()), ("class", {"internal", "data"}, "val a: Int"))
        self.assertEqual(base.mods, {"abstract"})
        self.assertIn("ViewModel()", base.supertypes)
        self.assertEqual((handler.kind, handler.mods), ("interface", {"fun"}))
        self.assertEqual(preview.line, 6)
        self.assertEqual(preview.first_line, 4)

    def test_a_type_parameter_bound_is_not_the_supertype_colon(self):
        _, (d,) = k.parse("class A<T : Comparable<T>>(val x: T) : Base()\n")
        self.assertIn("Base()", d.supertypes)
        self.assertNotIn("Comparable", d.supertypes)


class CleanAppTest(unittest.TestCase):
    def test_a_conforming_app_has_no_violations(self):
        self.assertEqual(lint_app(), [])

    def test_test_sources_and_build_output_are_not_checked(self):
        bad = "package com.x\n\nclass FooViewModel : ViewModel()\n"
        v = lint_app(outside={
            "app/src/test/kotlin/FooViewModelTest.kt": bad,
            "app/src/androidTest/kotlin/Bar.kt": bad,
            "app/build/generated/Baz.kt": bad,
        })
        self.assertEqual(v, [])


class PageFilesTest(unittest.TestCase):
    def test_page1_a_page_declaration_in_a_file_with_another_name(self):
        v = lint_app({"Home.kt": CLEAN["HomeUiState.kt"].replace("HomeUiState", "HomeUiState")}, remove=("HomeUiState.kt",))
        assert_rule(self, v, "PAGE-1", "`HomeUiState` is in Home.kt")

    def test_page1_a_second_public_declaration_in_the_file_of_a_page_part(self):
        extra = {"HomeViewModel.kt": CLEAN["HomeViewModel.kt"] + "\nsealed interface HomeEvent\n"}
        assert_rule(self, lint_app(extra), "PAGE-1", "`HomeEvent`")

    def test_page1_private_helpers_and_nested_types_are_fine(self):
        text = CLEAN["HomeViewModel.kt"].replace(
            "fun refresh() {}", "sealed interface Event\n    fun refresh() {}") + "\nprivate fun helper() = 1\n"
        self.assertEqual(lint_app({"HomeViewModel.kt": text}), [])

    def test_page1_a_file_named_for_a_page_part_must_declare_it(self):
        v = lint_app({"SettingsViewModel.kt": "package com.x.ui\n\nval settings = 1\n"})
        assert_rule(self, v, "PAGE-1", "does not declare `SettingsViewModel`")

    def test_page1_the_screenshot_package_is_left_to_its_own_rules(self):
        shot = '''
            package com.x.screenshot

            @Preview
            @Composable
            private fun HomePageScreenshot() {
                AppTheme { HomePageContent(state = HomeUiState("a"), onRefresh = {}, onOpen = {}) }
            }
        '''
        self.assertEqual(lint_app(outside={"app/src/debug/kotlin/com/x/screenshot/HomePage.kt": textwrap.dedent(shot)}), [])

    def test_page2_a_page_without_content_and_content_without_a_page(self):
        assert_rule(self, lint_app(remove=("HomePageContent.kt",)), "PAGE-2", "no `HomePageContent`")
        assert_rule(self, lint_app(remove=("HomePage.kt",)), "PAGE-2", "no `HomePage`")

    def test_page2_the_content_must_be_in_the_package_of_the_page(self):
        moved = CLEAN["HomePageContent.kt"].replace("package com.x.ui", "package com.x.other")
        assert_rule(self, lint_app({"HomePageContent.kt": moved}), "PAGE-2")

    def test_page3_visibility(self):
        private_page = CLEAN["HomePage.kt"].replace("fun HomePage", "private fun HomePage")
        assert_rule(self, lint_app({"HomePage.kt": private_page}), "PAGE-3", "public")
        public_content = CLEAN["HomePageContent.kt"].replace("internal fun", "fun")
        assert_rule(self, lint_app({"HomePageContent.kt": public_content}), "PAGE-3", "`internal`")
        private_content = CLEAN["HomePageContent.kt"].replace("internal fun", "private fun")
        assert_rule(self, lint_app({"HomePageContent.kt": private_content}), "PAGE-3", "`internal`")

    def test_page4_screen_view_and_content_names_of_a_page(self):
        screen = "package com.x.ui\n\n@Composable\nfun HomeScreen() {}\n"
        assert_rule(self, lint_app({"HomeScreen.kt": screen}), "PAGE-4", "never a `Screen`")
        content = "package com.x.ui\n\n@Composable\nfun HomeContent() {}\n"
        assert_rule(self, lint_app({"HomeContent.kt": content}), "PAGE-4", "HomePageContent")
        view = "package com.x.ui\n\n@Composable\nfun HomeView() {}\n"
        assert_rule(self, lint_app({"HomeView.kt": view}), "PAGE-4", "HomePageContent")

    def test_page4_a_content_composable_of_something_that_is_not_a_page_is_fine(self):
        text = "package com.x.ui\n\n@Composable\nfun CardContent() {}\n"
        self.assertNotIn("PAGE-4", rules(lint_app({"CardContent.kt": text})))

    def test_page4_page_and_screen_viewmodels(self):
        vm = "package com.x.ui\n\nclass HomePageViewModel : ViewModel()\n"
        assert_rule(self, lint_app({"HomePageViewModel.kt": vm}), "PAGE-4", "HomeViewModel")
        vm = "package com.x.ui\n\nclass HomeScreenViewModel : ViewModel()\n"
        assert_rule(self, lint_app({"HomeScreenViewModel.kt": vm}), "PAGE-4", "HomeViewModel")

    def test_page5_the_page_calls_its_content_exactly_once(self):
        none = CLEAN["HomePage.kt"].replace("HomePageContent(", "other(")
        assert_rule(self, lint_app({"HomePage.kt": none}), "PAGE-5", "0 times")
        twice = CLEAN["HomePage.kt"].replace("    HomePageContent(", "    HomePageContent(state = state, onRefresh = {}, onOpen = {})\n    HomePageContent(")
        assert_rule(self, lint_app({"HomePage.kt": twice}), "PAGE-5", "2 times")

    def test_page5_the_page_has_no_preview_and_no_ui_imports(self):
        preview = CLEAN["HomePage.kt"] + "\n@Preview\n@Composable\nprivate fun Preview() {}\n"
        assert_rule(self, lint_app({"HomePage.kt": preview}), "PAGE-5", "@Preview")
        imports = CLEAN["HomePage.kt"].replace("import org.koin", "import androidx.compose.foundation.layout.Column\nimport org.koin")
        assert_rule(self, lint_app({"HomePage.kt": imports}), "PAGE-5", "androidx.compose.foundation.layout.Column")
        material = CLEAN["HomePage.kt"].replace("import org.koin", "import androidx.compose.material3.Text\nimport org.koin")
        assert_rule(self, lint_app({"HomePage.kt": material}), "PAGE-5", "material3")

    def test_page6_the_content_is_stateless(self):
        for body, what in (
            ("val vm = homeViewModel", "a ViewModel"),
            ("val x = koinInject<Foo>()", "Koin"),
            ("val s = flow.collectAsState()", "a Flow"),
            ("val f: StateFlow<Int> = x", "a Flow"),
            ("backStack.add(1)", "the navigation"),
            ("val r: HomeRepository = x", "a repository"),
        ):
            text = CLEAN["HomePageContent.kt"].replace("Text(state.title)", f"Text(state.title)\n    {body}")
            assert_rule(self, lint_app({"HomePageContent.kt": text}), "PAGE-6", what)

    def test_page6_a_layout_named_flow_is_not_a_flow(self):
        text = CLEAN["HomePageContent.kt"].replace("Text(state.title)", "FlowRow { Text(state.title) }")
        self.assertEqual(lint_app({"HomePageContent.kt": text}), [])

    def test_page6_the_content_takes_the_ui_state_of_its_page(self):
        text = CLEAN["HomePageContent.kt"].replace("state: HomeUiState", "title: String").replace("state.title", "title").replace(
            "state = HomeUiState(\"a\")", "title = \"a\"").replace("state = HomeUiState(\"\")", "title = \"\"")
        assert_rule(self, lint_app({"HomePageContent.kt": text}), "PAGE-6", "HomeUiState")


class ViewModelTest(unittest.TestCase):
    def test_vm1_a_viewmodel_is_requested_only_in_a_page(self):
        text = "package com.x.ui\n\n@Composable\nfun Other() {\n    val vm = koinViewModel<HomeViewModel>()\n}\n"
        assert_rule(self, lint_app({"Other.kt": text}), "VM-1", "outside an `XPage`")

    def test_vm1_a_page_requests_its_own_viewmodel(self):
        text = CLEAN["HomePage.kt"].replace("koinViewModel<HomeViewModel>", "koinViewModel<SettingsViewModel>")
        assert_rule(self, lint_app({"HomePage.kt": text}), "VM-1", "its ViewModel is `HomeViewModel`")

    def test_vm1_the_type_must_be_visible(self):
        text = CLEAN["HomePage.kt"].replace("val viewModel = koinViewModel<HomeViewModel>()", "val viewModel = koinViewModel()")
        assert_rule(self, lint_app({"HomePage.kt": text}), "VM-1", "needs its type")
        typed = CLEAN["HomePage.kt"].replace("val viewModel = koinViewModel<HomeViewModel>()",
                                             "val viewModel: HomeViewModel = koinViewModel()")
        self.assertEqual(lint_app({"HomePage.kt": typed}), [])

    def test_vm1_every_lookup_form_is_a_request(self):
        for call in ("viewModel<HomeViewModel>()", "getViewModel<HomeViewModel>()", "hiltViewModel<HomeViewModel>()",
                     "koinNavViewModel<HomeViewModel>()", "viewModels<HomeViewModel>()"):
            text = f"package com.x.ui\n\n@Composable\nfun Other() {{\n    val vm = {call}\n}}\n"
            assert_rule(self, lint_app({"Other.kt": text}), "VM-1")

    def test_vm1_a_page_with_arguments_passes_them_in_parameters(self):
        text = CLEAN["HomePage.kt"].replace("koinViewModel<HomeViewModel>()", "koinViewModel<HomeViewModel>(parameters = { parametersOf(id) })")
        self.assertEqual(lint_app({"HomePage.kt": text}), [])

    def test_vm1_the_trailing_lambda_form_is_a_request_too(self):
        for call in ("koinViewModel { parametersOf(id) }", "koinViewModel<HomeViewModel> { parametersOf(id) }",
                     "koinViewModel<HomeViewModel>(key = \"a\") { parametersOf(id) }"):
            text = f"package com.x.ui\n\n@Composable\nfun Other() {{\n    val vm = {call}\n}}\n"
            assert_rule(self, lint_app({"Other.kt": text}), "VM-1")
        inside = CLEAN["HomePage.kt"].replace("koinViewModel<HomeViewModel>()", "koinViewModel<HomeViewModel> { parametersOf(id) }")
        self.assertEqual(lint_app({"HomePage.kt": inside}), [])
        wrong = CLEAN["HomePage.kt"].replace("koinViewModel<HomeViewModel>()", "koinViewModel<ShareViewModel> { parametersOf(id) }")
        assert_rule(self, lint_app({"HomePage.kt": wrong}), "VM-1", "its ViewModel is `HomeViewModel`")

    def test_vm1_a_koin_definition_with_a_type_and_a_lambda_is_not_a_request(self):
        text = "package com.x.ui\n\nval m = module {\n    viewModel<HomeViewModel> { HomeViewModel(get()) }\n}\n"
        self.assertEqual(lint_app({"AppModule.kt": text}), [])

    def test_vm1_a_function_of_the_file_called_like_a_lookup_is_not_one(self):
        text = ("package com.x.ui\n\nobject KoinModule {\n    val modules = listOf(getViewModel())\n"
                "    private fun getViewModel() = module { viewModelOf(::HomeViewModel) }\n}\n")
        self.assertEqual(lint_app({"KoinModule.kt": text}), [])

    def test_vm2_two_pages_requesting_one_viewmodel(self):
        detail = CLEAN["HomePage.kt"].replace("HomePageContent(", "DetailPageContent(").replace("fun HomePage", "fun DetailPage")
        v = lint_app({
            "DetailPage.kt": detail,
            "DetailPageContent.kt": CLEAN["HomePageContent.kt"].replace("HomePageContent", "DetailPageContent"),
            "DetailUiState.kt": CLEAN["HomeUiState.kt"].replace("HomeUiState", "DetailUiState"),
        })
        assert_rule(self, v, "VM-2", "`HomePage`")
        assert_rule(self, v, "VM-2", "`DetailPage`")

    def test_vm2_a_page_may_request_its_viewmodel_more_than_once(self):
        text = CLEAN["HomePage.kt"].replace("    val state", "    val again = koinViewModel<HomeViewModel>()\n    val state")
        self.assertNotIn("VM-2", rules(lint_app({"HomePage.kt": text})))

    def test_vm3_viewmodels_scoped_to_something_shared(self):
        for call in ("activityViewModel<HomeViewModel>()", "koinActivityViewModel<HomeViewModel>()",
                     "sharedViewModel<HomeViewModel>(navController)", "koinViewModel<HomeViewModel>(viewModelStoreOwner = owner)",
                     "hiltViewModel<HomeViewModel>(parentEntry)", "koinViewModel<HomeViewModel>(navBackStackEntry)"):
            text = CLEAN["HomePage.kt"].replace("koinViewModel<HomeViewModel>()", call)
            assert_rule(self, lint_app({"HomePage.kt": text}), "VM-3")

    def test_vm3_standalone_owner_arguments(self):
        text = CLEAN["HomePage.kt"].replace("    val state", "    val owner = LocalViewModelStoreOwner.current\n    val state")
        assert_rule(self, lint_app({"HomePage.kt": text}), "VM-3", "LocalViewModelStoreOwner")

    def test_vm4_a_viewmodel_is_not_a_single_factory_or_scoped(self):
        for definition in ("single { HomeViewModel(get()) }", "singleOf(::HomeViewModel)", "factory<HomeViewModel> { HomeViewModel(get()) }",
                           "factoryOf(::HomeViewModel)", "scoped { HomeViewModel(get()) }", "scopedOf(::HomeViewModel)"):
            text = f"package com.x.ui\n\nval m = module {{\n    {definition}\n}}\n"
            assert_rule(self, lint_app({"AppModule.kt": text}), "VM-4")

    def test_vm4_other_singles_and_viewmodel_definitions_are_fine(self):
        text = "package com.x.ui\n\nval m = module {\n    viewModelOf(::HomeViewModel)\n    single { HomeRepository(get()) }\n    singleOf(::Settings)\n}\n"
        self.assertEqual(lint_app({"AppModule.kt": text}), [])

    def test_vm5_a_viewmodel_holding_another(self):
        text = CLEAN["HomeViewModel.kt"].replace("HomeRepository)", "HomeRepository, private val settings: SettingsViewModel)")
        assert_rule(self, lint_app({"HomeViewModel.kt": text}), "VM-5", "`SettingsViewModel`")
        text = CLEAN["HomeViewModel.kt"].replace("fun refresh() {}", "fun refresh() { get<SettingsViewModel>() }")
        assert_rule(self, lint_app({"HomeViewModel.kt": text}), "VM-5")

    def test_vm5_a_base_class_is_not_a_held_viewmodel(self):
        text = CLEAN["HomeViewModel.kt"].replace("ViewModel() {", "BaseViewModel() {")
        self.assertEqual(lint_app({"HomeViewModel.kt": text, "BaseViewModel.kt": "package com.x.ui\n\nabstract class BaseViewModel : ViewModel()\n"}), [])

    def test_vm6_a_viewmodel_is_named_for_its_page(self):
        text = "package com.x.ui\n\nclass HomeModel : ViewModel()\n"
        assert_rule(self, lint_app({"HomeModel.kt": text}), "VM-6", "name it `XViewModel`")

    def test_vm6_a_viewmodel_needs_its_page(self):
        text = "package com.x.ui\n\nclass SettingsViewModel : ViewModel()\n"
        assert_rule(self, lint_app({"SettingsViewModel.kt": text}), "VM-6", "no `SettingsPage`")

    def test_vm6_abstract_base_classes_need_no_page(self):
        text = "package com.x.ui\n\nabstract class BaseViewModel : ViewModel()\n"
        self.assertEqual(lint_app({"BaseViewModel.kt": text}), [])

    ROOT = (
        "package com.x.ui\n\nimport org.koin.compose.koinInject\n\n@Composable\nfun Root() {\n"
        "    val coordinator: RootCoordinator = koinInject()\n    Text(coordinator.title)\n}\n"
    )
    COORDINATOR = "package com.x.ui\n\nclass RootCoordinator {\n    val title = \"x\"\n}\n"

    def test_root_may_be_state_driven_through_a_coordinator_that_is_not_a_viewmodel(self):
        self.assertEqual(lint_app({"Root.kt": self.ROOT, "RootCoordinator.kt": self.COORDINATOR}), [])

    def test_root_requests_no_viewmodel(self):
        text = self.ROOT.replace("RootCoordinator = koinInject()", "RootViewModel = koinViewModel()")
        assert_rule(self, lint_app({"Root.kt": text}), "VM-1", "outside an `XPage`")

    def test_a_viewmodel_of_the_root_is_a_viewmodel_of_a_page_like_any_other(self):
        vm = "package com.x.ui\n\nclass RootViewModel : ViewModel()\n"
        assert_rule(self, lint_app({"RootViewModel.kt": vm}), "VM-6", "no `RootPage`")

    def test_vm7_no_shared_flow_in_a_viewmodel(self):
        text = CLEAN["HomeViewModel.kt"].replace("private val events = Channel<String>(Channel.BUFFERED)",
                                                  "private val events = MutableSharedFlow<String>()")
        assert_rule(self, lint_app({"HomeViewModel.kt": text}), "VM-7", "MutableSharedFlow")


class UiStateTest(unittest.TestCase):
    def test_ui1_a_state_needs_its_page(self):
        text = "package com.x.ui\n\ndata class SettingsUiState(val a: Int)\n"
        assert_rule(self, lint_app({"SettingsUiState.kt": text}), "UI-1", "no `SettingsPage`")

    def test_ui2_a_state_is_immutable(self):
        for body in ("var title: String", "val items: MutableList<String>", "val items: ArrayList<String> = ArrayList()",
                     "val s = mutableStateOf(1)"):
            text = f"package com.x.ui\n\ndata class HomeUiState(\n    {body},\n)\n"
            assert_rule(self, lint_app({"HomeUiState.kt": text}), "UI-2")

    def test_ui2_a_sealed_state_with_val_properties_is_fine(self):
        text = ("package com.x.ui\n\nsealed interface HomeUiState {\n    data object Loading : HomeUiState\n"
                "    data class Loaded(val items: List<String>) : HomeUiState\n}\n")
        self.assertEqual(lint_app({"HomeUiState.kt": text}), [])

    def test_ui3_a_state_holds_no_flow_or_channel(self):
        for body in ("val updates: Flow<Int>", "val events: Channel<Int>", "val s: StateFlow<Int>"):
            text = f"package com.x.ui\n\ndata class HomeUiState(\n    {body},\n)\n"
            assert_rule(self, lint_app({"HomeUiState.kt": text}), "UI-3")


class PreviewTest(unittest.TestCase):
    def test_prv1_the_content_has_a_private_preview_named_preview(self):
        no_preview = CLEAN["HomePageContent.kt"].split("@Preview")[0]
        assert_rule(self, lint_app({"HomePageContent.kt": no_preview}), "PRV-1")
        only_dark = CLEAN["HomePageContent.kt"].replace("private fun Preview()", "private fun PreviewDark()")
        assert_rule(self, lint_app({"HomePageContent.kt": only_dark}), "PRV-1")
        public = CLEAN["HomePageContent.kt"].replace("private fun Preview()", "fun Preview()")
        assert_rule(self, lint_app({"HomePageContent.kt": public}), "PRV-1")

    def test_prv2_a_preview_is_private_and_named_preview(self):
        public = CLEAN["HomeCard.kt"].replace("private fun", "fun")
        assert_rule(self, lint_app({"HomeCard.kt": public}), "PRV-2", "`private`")
        renamed = CLEAN["HomeCard.kt"].replace("fun Preview()", "fun HomeCardPreview()")
        assert_rule(self, lint_app({"HomeCard.kt": renamed}), "PRV-2", "named `Preview`")
        lower = CLEAN["HomeCard.kt"].replace("fun Preview()", "fun Previews()")
        assert_rule(self, lint_app({"HomeCard.kt": lower}), "PRV-2")

    def test_prv2_a_name_once_per_file(self):
        twice = CLEAN["HomeCard.kt"] + "\n@Preview\n@Composable\nprivate fun Preview() {\n    AppTheme { HomeCard(\"b\") }\n}\n"
        assert_rule(self, lint_app({"HomeCard.kt": twice}), "PRV-2", "more than once")

    def test_prv3_the_preview_is_in_the_file_of_its_composable(self):
        other = CLEAN["HomeCard.kt"].replace("HomeCard(\"a\")", "SomethingElse(\"a\")")
        assert_rule(self, lint_app({"HomeCard.kt": other}), "PRV-3", "does not show a composable of HomeCard.kt")
        alone = "package com.x.ui\n\n@Preview\n@Composable\nprivate fun Preview() {\n    AppTheme { HomeCard(\"a\") }\n}\n"
        assert_rule(self, lint_app({"Previews.kt": alone}), "PRV-3", "previews nothing")

    def test_prv3_a_preview_may_show_a_private_helper_of_the_file(self):
        text = CLEAN["HomeCard.kt"].replace("AppTheme { HomeCard(\"a\") }", "AppTheme { Helper() }") + (
            "\n@Composable\nprivate fun Helper() {}\n")
        self.assertEqual(lint_app({"HomeCard.kt": text}), [])

    def test_prv4_the_preview_is_wrapped_in_the_theme(self):
        bare = CLEAN["HomeCard.kt"].replace("AppTheme { HomeCard(\"a\") }", "HomeCard(\"a\")")
        assert_rule(self, lint_app({"HomeCard.kt": bare}), "PRV-4")

    def test_prv5_a_preview_needs_no_koin_viewmodel_or_flow(self):
        for body in ("val vm = koinViewModel<HomeViewModel>()", "val x = koinInject<Foo>()",
                     "val s = flow.collectAsState()", "val vm = HomeViewModel(Fake())"):
            text = CLEAN["HomeCard.kt"].replace("    AppTheme {", f"    {body}\n    AppTheme {{")
            assert_rule(self, lint_app({"HomeCard.kt": text}), "PRV-5")

    def test_prv5_a_url_needs_the_preview_handler(self):
        url = CLEAN["HomeCard.kt"].replace("HomeCard(\"a\")", "HomeCard(\"https://example.com/a.png\")")
        assert_rule(self, lint_app({"HomeCard.kt": url}), "PRV-5", "LocalAsyncImagePreviewHandler")
        handled = url.replace("    AppTheme {", "    val h = LocalAsyncImagePreviewHandler\n    AppTheme {")
        self.assertNotIn("PRV-5", rules(lint_app({"HomeCard.kt": handled})))

    def test_prv6_screenshots_only_in_the_screenshot_package(self):
        text = CLEAN["HomeCard.kt"].replace("fun Preview()", "fun HomeCardScreenshot()")
        assert_rule(self, lint_app({"HomeCard.kt": text}), "PRV-6", "belongs in the `screenshot` package")

    def test_prv6_every_preview_of_the_package_is_a_screenshot(self):
        text = textwrap.dedent('''
            package com.x.screenshot

            @Preview
            @Composable
            private fun HomePage() {
                AppTheme { HomePageContent(state = HomeUiState("a"), onRefresh = {}, onOpen = {}) }
            }
        ''')
        v = lint_app(outside={"app/src/debug/kotlin/com/x/screenshot/HomePage.kt": text})
        assert_rule(self, v, "PRV-6", "ends in `Screenshot`")

    def test_prv4_and_prv5_apply_to_screenshots(self):
        text = textwrap.dedent('''
            package com.x.screenshot

            @Preview
            @Composable
            private fun HomePageScreenshot() {
                val vm = koinViewModel<HomeViewModel>()
                HomePageContent(state = HomeUiState("a"), onRefresh = {}, onOpen = {})
            }
        ''')
        v = lint_app(outside={"app/src/debug/kotlin/com/x/screenshot/HomePage.kt": text})
        assert_rule(self, v, "PRV-4")
        assert_rule(self, v, "PRV-5")

    def test_prv7_every_public_or_internal_composable_has_a_preview_however_short(self):
        for visibility in ("", "internal "):
            text = f"package com.x.ui\n\n@Composable\n{visibility}fun Small() {{\n    Text(\"a\")\n}}\n"
            assert_rule(self, lint_app({"Small.kt": text}), "PRV-7", "`Small`")

    def test_prv7_one_that_needs_the_camera_koin_or_a_viewmodel_has_one_too_mocked(self):
        for body in ("val camera = rememberCamera()", "val x = koinInject<Foo>()", "val vm = koinViewModel<FooViewModel>()"):
            text = f"package com.x.ui\n\n@Composable\ninternal fun Cam() {{\n    {body}\n}}\n"
            assert_rule(self, lint_app({"Cam.kt": text}), "PRV-7", "`Cam`")

    def test_prv7_a_private_composable_and_the_shell_need_no_preview(self):
        private = "package com.x.ui\n\n@Composable\nprivate fun Small() {\n    Text(\"a\")\n}\n"
        self.assertNotIn("PRV-7", rules(lint_app({"Small.kt": private})))
        for name in ("Root", "AppNavigation", "Router", "AppTheme"):
            text = f"package com.x.ui\n\n@Composable\nfun {name}() {{\n    koinInject<Foo>()\n    NavDisplay()\n}}\n"
            self.assertNotIn("PRV-7", rules(lint_app({f"{name}.kt": text})), name)

    def test_prv7_a_composable_that_returns_a_value_has_nothing_to_preview(self):
        body = "\n".join(f"    val a{i} = {i}" for i in range(12))
        text = f"package com.x.ui\n\n@Composable\nfun rememberThing(key: Int): Thing {{\n{body}\n    return Thing()\n}}\n"
        self.assertNotIn("PRV-7", rules(lint_app({"rememberThing.kt": text})))

    def test_a_public_preview_named_like_a_page_is_a_preview_not_a_page(self):
        text = ("package com.x.ui\n\n@Preview\n@Composable\nfun PreviewHomePage() {\n"
                "    AppTheme { HomePageContent(state = HomeUiState(\"a\"), onRefresh = {}, onOpen = {}) }\n}\n")
        v = lint_app({"HomePageContent.kt": CLEAN["HomePageContent.kt"] + "\n" + text.split("package com.x.ui\n\n")[1]})
        self.assertEqual(rules(v), ["PRV-2"])

    def test_prv7_a_composable_with_a_preview_is_fine(self):
        text = ("package com.x.ui\n\n@Composable\ninternal fun Small() {\n    Text(\"a\")\n}\n\n"
                "@Preview\n@Composable\nprivate fun Preview() {\n    AppTheme { Small() }\n}\n")
        self.assertEqual(lint_app({"Small.kt": text}), [])


class ComposableFilesTest(unittest.TestCase):
    def test_cmp1_one_public_composable_per_file(self):
        text = CLEAN["HomeCard.kt"].replace("@Preview", "@Composable\ninternal fun Badge() {}\n\n@Preview", 1)
        assert_rule(self, lint_app({"HomeCard.kt": text}), "CMP-1", "2 public composables")

    def test_cmp1_private_helpers_are_free(self):
        text = CLEAN["HomeCard.kt"].replace("@Preview", "@Composable\nprivate fun Badge() {}\n\n@Preview", 1)
        self.assertEqual(lint_app({"HomeCard.kt": text}), [])

    def test_cmp1_the_file_is_named_after_the_composable(self):
        assert_rule(self, lint_app({"Cards.kt": CLEAN["HomeCard.kt"]}, remove=("HomeCard.kt",)), "CMP-1", "name the file after")


class ScreenshotPackageTest(unittest.TestCase):
    PACKAGE = "app/src/debug/kotlin/com/x/screenshot/"
    GOOD = textwrap.dedent('''
        package com.x.screenshot

        @Preview
        @Composable
        private fun HomePageScreenshot() {
            AppTheme { HomePageContent(state = HomeUiState("a"), onRefresh = {}, onOpen = {}) }
        }
    ''')

    def test_shot1_nothing_is_shared(self):
        shared = self.GOOD + "\nval sample = HomeUiState(\"a\")\n"
        assert_rule(self, lint_app(outside={self.PACKAGE + "HomePage.kt": shared}), "SHOT-1", "val sample")

    def test_shot2_the_order_file_is_checked_for_an_app_with_a_readme_yml(self):
        files = {self.PACKAGE + "HomePage.kt": self.GOOD, "readme.yml": "name: X\n"}
        assert_rule(self, lint_app(outside=files), "SHOT-2", "order.txt")
        files[self.PACKAGE + "order.txt"] = "HomePage\n"
        self.assertEqual(lint_app(outside=files), [])

    def test_shot2_an_app_without_a_readme_yml_is_not_asked_for_one_yet(self):
        self.assertEqual(lint_app(outside={self.PACKAGE + "HomePage.kt": self.GOOD}), [])


class IgnoreTest(unittest.TestCase):
    def bad(self, comment_above="", comment_on=""):
        text = CLEAN["HomeUiState.kt"].replace("data class", f"{comment_above}data class").replace(
            "emptyList())", f"emptyList(), var n: Int = 0){comment_on}")
        return lint_app({"HomeUiState.kt": text})

    def test_a_violation_is_silenced_by_a_comment_with_a_reason(self):
        self.assertIn("UI-2", rules(self.bad()))
        self.assertEqual(self.bad(comment_above="// lint:ignore UI-2: a counter the page edits in place\n"), [])
        self.assertEqual(self.bad(comment_on=" // lint:ignore UI-2: a counter the page edits in place"), [])

    def test_a_comment_without_a_reason_silences_nothing(self):
        v = self.bad(comment_above="// lint:ignore UI-2\n")
        self.assertEqual(rules(v), ["IGNORE-1", "UI-2"])

    def test_a_comment_for_another_rule_or_an_unknown_one_silences_nothing(self):
        self.assertEqual(rules(self.bad(comment_above="// lint:ignore UI-3: wrong rule\n")), ["UI-2"])
        self.assertEqual(rules(self.bad(comment_above="// lint:ignore NOPE-9: why\n")), ["IGNORE-1", "UI-2"])

    def test_an_ignore_in_a_string_is_not_a_comment(self):
        text = CLEAN["HomeUiState.kt"].replace("emptyList())", 'emptyList(), var n: Int = 0, val s: String = "// lint:ignore UI-2: x")')
        self.assertIn("UI-2", rules(lint_app({"HomeUiState.kt": text})))


# The Koin setup of a conforming app: every app has one, and the Koin rules (test_conventions_di.py) are checked on the whole app
KOIN = {
    "app/src/main/kotlin/com/x/di/KoinModules.kt": """
        package com.x.di

        object KoinModules {
            private val data = module {
                viewModelOf(::HomeViewModel)
                singleOf(::HomeRepository)
            }
            val modules: List<Module> = listOf(data)
        }
    """,
    "app/src/main/kotlin/com/x/App.kt": """
        package com.x

        import org.koin.core.context.startKoin

        class App { fun start() { startKoin { modules(KoinModules.modules) } } }
    """,
}


class CommandTest(unittest.TestCase):
    def run_main(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            for path, text in files.items():
                target = Path(tmp) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(textwrap.dedent(text).lstrip("\n"))
            out, summary = io.StringIO(), Path(tmp) / "summary.md"
            os.environ["GITHUB_STEP_SUMMARY"] = str(summary)
            try:
                with redirect_stdout(out):
                    code = lc.main([tmp])
            finally:
                del os.environ["GITHUB_STEP_SUMMARY"]
            return code, out.getvalue(), summary.read_text()

    def test_a_clean_app_exits_zero(self):
        code, out, summary = self.run_main({**{UI + n: t for n, t in CLEAN.items()}, **KOIN})
        self.assertEqual(code, 0)
        self.assertIn("no violations", out)
        self.assertIn("No violations", summary)

    def test_violations_exit_one_with_annotations_and_a_summary(self):
        files = {UI + n: t for n, t in CLEAN.items()}
        files[UI + "HomeUiState.kt"] = "package com.x.ui\n\ndata class HomeUiState(var title: String)\n"
        code, out, summary = self.run_main(files)
        self.assertEqual(code, 1)
        self.assertIn("::error file=app/src/main/kotlin/com/x/ui/HomeUiState.kt,line=3,title=UI-2::", out)
        self.assertIn("| `UI-2` |", summary)

    def test_an_app_without_kotlin_has_no_koin(self):
        code, out, _ = self.run_main({"README.md": "# x\n"})
        self.assertEqual(code, 1)
        self.assertIn("title=DI-1::", out)

    def test_every_rule_is_documented_and_every_documented_rule_exists(self):
        docs = (Path(__file__).resolve().parent.parent / "docs" / "lint.md").read_text()
        documented = set(__import__("re").findall(r"`((?:DI|NAME|PAGE|VM|UI|SHEET|PRV|CMP|SHOT|IGNORE)-\d+)`", docs))
        self.assertEqual(documented, set(lc.all_rules()))


SHEET = """
    package com.x.ui

    @Composable
    internal fun PickSheet(onDismiss: () -> Unit, onPick: (String) -> Unit) {
        ModalBottomSheet(onDismissRequest = onDismiss) {
            PickSheetContent(onPick = onPick)
        }
    }

    @Preview
    @Composable
    private fun Preview() {
        AppTheme { PickSheet(onDismiss = {}, onPick = {}) }
    }
"""
SHEET_CONTENT = """
    package com.x.ui

    @Composable
    internal fun PickSheetContent(onPick: (String) -> Unit) {
        Text("Pick")
    }

    @Preview
    @Composable
    private fun Preview() {
        AppTheme { PickSheetContent(onPick = {}) }
    }
"""
SHEETS = {"PickSheet.kt": SHEET, "PickSheetContent.kt": SHEET_CONTENT}


class SheetTest(unittest.TestCase):
    def test_a_sheet_with_its_content_passes(self):
        self.assertEqual(lint_app(SHEETS), [])

    def test_a_sheet_without_content_is_sheet_1(self):
        found = lint_app({"PickSheet.kt": SHEET})
        assert_rule(self, found, "SHEET-1", "has no `PickSheetContent`")

    def test_a_sheet_that_does_not_call_its_content_is_sheet_1(self):
        sheet = SHEET.replace("PickSheetContent(onPick = onPick)", "Text(\"inline\")")
        found = lint_app({"PickSheet.kt": sheet, "PickSheetContent.kt": SHEET_CONTENT})
        assert_rule(self, found, "SHEET-1", "does not call `PickSheetContent`")

    def test_content_without_a_sheet_is_sheet_2(self):
        assert_rule(self, lint_app({"PickSheetContent.kt": SHEET_CONTENT}), "SHEET-2", "has no `PickSheet`")

    def test_a_bottom_sheet_outside_an_xsheet_is_sheet_3(self):
        card = """
            package com.x.ui

            @Composable
            internal fun HomeCard(title: String) {
                ModalBottomSheet(onDismissRequest = {}) { Text(title) }
            }

            @Preview
            @Composable
            private fun Preview() {
                AppTheme { HomeCard("a") }
            }
        """
        assert_rule(self, lint_app({"HomeCard.kt": card}), "SHEET-3", "only drawn inside an `XSheet`")

    def test_a_private_helper_of_the_sheet_may_draw_it(self):
        sheet = SHEET.replace("    @Preview", "    @Composable\n    private fun Frame(content: @Composable () -> Unit) {\n"
                                                "        ModalBottomSheet(onDismissRequest = {}) { content() }\n    }\n\n    @Preview")
        self.assertEqual([v for v in lint_app({"PickSheet.kt": sheet, "PickSheetContent.kt": SHEET_CONTENT}) if v.rule == "SHEET-3"], [])

    def test_content_that_knows_the_sheet_is_sheet_4(self):
        content = SHEET_CONTENT.replace('Text("Pick")', "SheetLayout(onClose = {}) { Text(\"Pick\") }")
        assert_rule(self, lint_app({"PickSheet.kt": SHEET, "PickSheetContent.kt": content}), "SHEET-4", "SheetLayout")

    def test_content_that_draws_the_sheet_is_sheet_4(self):
        content = SHEET_CONTENT.replace('Text("Pick")', "ModalBottomSheet(onDismissRequest = {}) { Text(\"Pick\") }")
        assert_rule(self, lint_app({"PickSheet.kt": SHEET, "PickSheetContent.kt": content}), "SHEET-4", "ModalBottomSheet")

    def test_stateful_content_is_sheet_5(self):
        content = SHEET_CONTENT.replace('Text("Pick")', "val vm = koinViewModel<PickViewModel>()")
        assert_rule(self, lint_app({"PickSheet.kt": SHEET, "PickSheetContent.kt": content}), "SHEET-5")

    def test_content_without_its_own_preview_is_prv_1(self):
        content = SHEET_CONTENT.split("    @Preview")[0]
        assert_rule(self, lint_app({"PickSheet.kt": SHEET, "PickSheetContent.kt": content}), "PRV-1", "PickSheetContent")

    def test_a_sheet_in_the_screenshot_package_is_not_checked(self):
        shot = """
            package com.x.screenshot

            @Preview
            @Composable
            private fun SheetScreenshot() {
                AppTheme { ModalBottomSheet(onDismissRequest = {}) { Text("a") } }
            }
        """
        found = lint_app(outside={"app/src/main/java/com/x/screenshot/SheetScreenshot.kt": shot})
        self.assertEqual([v for v in found if v.rule.startswith("SHEET")], [])

if __name__ == "__main__":
    unittest.main()
