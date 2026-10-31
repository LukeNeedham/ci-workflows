# App conventions

The libraries and code patterns every app uses, beyond the architecture basics in
[new-app.md](new-app.md#5-app-architecture). Defaults for a normal app: if the user asks for something
else, do that instead. Check the current stable version of every library before adding it.

The architecture and naming rules here and in [new-app.md](new-app.md) are checked by CI on every PR: see [conventions-check.md](conventions-check.md).

- [Naming](#naming)
- [Libraries](#libraries)
- [Strings](#strings)
- [Theme](#theme)
- [Composables and previews](#composables-and-previews)
- [One-off events](#one-off-events)
- [Touch targets](#touch-targets)
- [Release builds](#release-builds)

## Naming

**An acronym or initialism is an ordinary word in a camel case or Pascal case name: only its first letter is a capital.**
`IosSdkManager`, not `iOSSDKManager`. This holds for every class, interface, object, function, property, parameter, file and
enum entry we write, whatever the acronym and however short:

| Not | But |
|---|---|
| `iOSSDKManager` | `IosSdkManager` |
| `HTTPClient`, `parseJSON` | `HttpClient`, `parseJson` |
| `UserDTO` | `UserDto` ([networking.md](networking.md#dtos-xdto)) |
| `UIState`, `userID` | `UiState`, `userId` |
| `URLBuilder`, `apiURL` | `UrlBuilder`, `apiUrl` |
| `HTMLParser`, `XMLNode` | `HtmlParser`, `XmlNode` |

Packages stay all lower case (`com.example.app.sdk`), and constants stay `UPPER_SNAKE_CASE` (`API_URL`), where the question does not
arise. The one exception is a name we do not choose: an override or a call of a library or platform API keeps the name it
has (`getURL()`, `Dispatchers.IO`), and a name a serialization format fixes is kept in `@SerialName`, not in our own
property name.

## Libraries

| Need | Use |
|---|---|
| Dependency injection | Koin ([new-app.md](new-app.md#5-app-architecture)) |
| Images | Coil 3 (`io.coil-kt.coil3`), `AsyncImage` |
| Serialization | `kotlinx.serialization` (also what Navigation 3 keys use) |
| Structured data | Room |
| Settings and small key-value data | DataStore (not `SharedPreferences`) |
| Networking | Ktor client with the OkHttp engine (`ktor-client-okhttp`), only for apps that make network calls. Models, mapping and the debug kit network log are in **[networking.md](networking.md)** |
| Date and time | `kotlinx-datetime` |
| Audio and video | Media3 (ExoPlayer) |

Do not add a second library for a job in this table. Anything else not listed is the app's own choice.

## Strings

**All user-visible text lives in `strings.xml`.** No hard-coded text in composables, ViewModels or
anywhere else: use `stringResource(R.string.…)` in composables, and pass a string resource id (or a
small sealed type) up from ViewModels rather than a finished `String`. This includes content
descriptions.

## Theme

Every app has its own `AppTheme`, set up by hand with a composition local. **The app never uses
`MaterialTheme`**: nothing in the app reads `MaterialTheme.colorScheme`, `.typography` or `.shapes`.
Everything reads `AppTheme.current` (or whatever the app names its local).

```kotlin
val LocalAppTheme = staticCompositionLocalOf<AppThemeValues> { error("No AppTheme provided") }

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalAppTheme provides AppThemeValues(/* … */), content = content)
}

object AppTheme {
    val current: AppThemeValues @Composable get() = LocalAppTheme.current
}
```

- The theme holds **colours** and **typefaces** (font families). Light and dark are decided here.
- **No fixed text styles.** Do not define a `titleLarge`-style scale. Each composable sets its own font
  size and line height inline, and takes only the typeface from the theme. Shared styles hide how
  big text really is where you read the code.
- If a Material 3 component is used, give it its colours explicitly from the app theme. The component
  must not fall back to `MaterialTheme` defaults.
- **The shared library's pages** use no Material either: the app maps its theme to a `DebugTheme` and
  passes it to `ProvideDebugSettings` ([using-the-library.md](using-the-library.md#the-theme-of-the-pages)).
  `ProvideDebugSettings` therefore goes *inside* `AppTheme`.

## Composables and previews

<a id="previews"></a>

- **One composable per file**, named after it, with its `@Preview` in the same file. Skip this for
  trivial composables (a few lines, used by one parent only): keep those next to their parent.
- **A preview is a `private` function in the file of its composable, named `Preview`.** A file with several previews
  (other data: empty, loading, error) keeps `Preview` for the main one and adds a differentiator to the others:
  `PreviewEmpty`, `PreviewLoading`. It is `private` so that the same name in every file never clashes, and the name says
  nothing about the composable because the file does. The previews of the `screenshot` package are the exception: they
  are named `XScreenshot`, since their names are unique across the package and become the images and the lines of
  `order.txt` ([screenshots.md](screenshots.md)).
- **The content of a bottom sheet is its own composable, in its own file, with its own preview**: `XSheetContent` in
  `XSheetContent.kt`, stateless and independent of the sheet (`XSheet`, which only draws the sheet around it), see [pages.md](pages.md).
- **Every composable has a preview, except trivial ones.** Previews wrap the content in `AppTheme` and
  use fake `UiState` / sample data, so they need no ViewModel, Koin or network.
- **Every page is an `XPage` and an `XPageContent`**, defined in [pages.md](pages.md): `XPage` holds its `XViewModel` and
  delegates all UI to the stateless, `internal` `XPageContent` (state down, events up), which always has at least one `private` general preview in its file
  (`private fun Preview()`), in the file `XPageContent.kt`; `XPage`, `XViewModel` and `XUiState` each have their own file too. Any README screenshots are separate (a page can have several, or none): a file per page that has some in the
  app's `screenshot` package, with its own mock data ([screenshots.md](screenshots.md)).

## One-off events

State goes in the `UiState` `StateFlow`. **One-off events** (navigate, show a snackbar, share) go
through a `Channel` the ViewModel exposes as a `Flow` (`Channel<Event>(Channel.BUFFERED)` with
`receiveAsFlow()`), collected once in the composable. Never put an event in `UiState`, and never use a
`SharedFlow` for it: an event with no collector, or two collectors, is lost or doubled.

## Touch targets

Everything clickable is **at least 48dp high and 48dp wide**, whatever it looks like. Use
`Modifier.minimumInteractiveComponentSize()` on the clickable element to guarantee it, rather than
sizing the visuals up.

## Release builds

Release builds enable minification: `isMinifyEnabled = true` (and `isShrinkResources = true`) in the
`release` build type, with `proguard-android-optimize.txt` and the app's `proguard-rules.pro`. Add
keep rules for what needs them (serialization, Room, reflection) and check a release build still
starts, because debug builds on CI do not exercise R8.
