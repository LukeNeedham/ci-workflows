<!-- The skeleton of an app's README.md (docs/readme.md). Copy it to the app's root, replace everything in
     <angle brackets>, delete these comments and write the text by hand. -->
<p align="center">
  <img src="app-icon.png" width="128" alt="<App name> icon">
</p>

# <App name>

<One line: what the app does.>

## Description

<What the app is and who it is for. One or two short paragraphs.>

## Features

- <Feature>
- <Feature>

## Screenshots

<!-- Optional: delete this section if there are none. -->
<img src="docs/screenshots/<name>.png" width="240" alt="<what it shows>">

## Getting started as a user

1. Install the latest build from the [AppHub](https://www.lukeneedham.com/apphub) app, or download the APK from
   the [Releases](../../releases) page.
2. Open the app. <First-run steps, if any.>

Requires Android <minimum version> or newer.

## Getting started as a developer

Requirements: JDK 17 and the Android SDK (platform 36), for example through Android Studio.

```
git clone https://github.com/LukeNeedham/<repo>.git
cd <repo>
./gradlew assembleDebug    # the APK is in app/build/outputs/apk/debug/
./gradlew test             # unit tests
```

Every pull request is built by CI, which comments on it with a link to install the APK.

## Project structure

- `app/`: <the app module; its main packages>
- <Anything else that is not obvious.>

<Architecture in a few lines.> See the
[shared conventions](https://github.com/LukeNeedham/ci-workflows/blob/main/docs/app-conventions.md).

## Contributing

Branch from `main`, make the change, and open a pull request. CI must be green before it is merged.

## License

<License name>. See [LICENSE](LICENSE).
