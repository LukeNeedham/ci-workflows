# Networking

**Only for apps that make network calls.** An app with none ignores this page: it has no DTOs, no Ktor client and no
network log to link up.

- [The stack](#the-stack)
- [DTOs: `XDto`](#dtos-xdto)
- [Defensive modeling](#defensive-modeling)
- [Map to a domain model](#map-to-a-domain-model)
- [The debug kit network log](#the-debug-kit-network-log)
- [Done checklist](#done-checklist)

## The stack

| Thing | Use |
|---|---|
| HTTP client | **Ktor client** (`ktor-client-core`, `ktor-client-content-negotiation`, `ktor-serialization-kotlinx-json`) |
| Engine | **OkHttp** (`ktor-client-okhttp`), so the client is `HttpClient(OkHttp) { ... }` |
| JSON | `kotlinx.serialization` ([app-conventions.md](app-conventions.md#libraries)) |

Do not add a second HTTP client or engine. The Ktor client is created once, declared in the Koin module of the
networking layer (`singleOf` / a `single { }`), and injected into the remote data sources, which are injected into the
repositories ([new-app.md](new-app.md#6-app-architecture)). Nothing outside the networking layer touches `HttpClient`.

## DTOs: `XDto`

**Every model that comes from the network is a DTO** (data transfer object): a `@Serializable` class that mirrors the
JSON of the API and nothing else. Its name is the name of the thing with the suffix **`Dto`**, capital D and lower-case `to`: `UserDto`,
`ArticleDto`, `LoginResponseDto`. Never `UserResponse`, `UserModel`, `UserDTO` or a bare `User`. Request bodies we send
follow the same rule (`LoginRequestDto`).

DTOs live in the networking layer (a `network` or `remote` package of their own), one per file. They hold no logic.

## Defensive modeling

**An API response can never crash the app.** The server can change, omit or break a field, and we do not control it, so
a DTO assumes nothing: **every property is optional, and has a default.**

```kotlin
@Serializable
data class UserDto(
    val id: String? = null,
    val name: String? = null,
    val age: Int? = null,
    val avatarUrl: String? = null,
    val roles: List<RoleDto>? = null,
    val status: String? = null,
)
```

- **Every property is nullable and defaults to `null`**, whatever the API docs say. Never a non-null property with no
  default: a missing field would throw `MissingFieldException`. Lists and maps are nullable too (`List<XDto>?`).
- **Enums arrive as a `String?`**, not as an enum: an unknown value would throw. The mapper turns it into the domain enum
  with a fallback (`Unknown`).
- **The `Json` is lenient**: `ignoreUnknownKeys = true`, `isLenient = true`, `coerceInputValues = true`
  (an unexpected `null` or unknown enum value becomes the default instead of throwing) and `explicitNulls = false`.

```kotlin
val json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    coerceInputValues = true
    explicitNulls = false
}

HttpClient(OkHttp) {
    install(ContentNegotiation) { json(json) }
    engine { addInterceptor(NetworkLogInterceptor()) }
}
```

- **A call that fails is a result, not a crash.** The data source catches the network and parsing errors of the call
  (not `CancellationException`), logs them with `Logger.e` and returns a failure the repository can handle.

## Map to a domain model

**A DTO never leaves the networking layer.** The repository (or the data source) maps each DTO to a **domain model** in a
mapper, and everything above it (ViewModels, `UiState`, composables, other repositories) only ever sees domain models.
The domain model is clean and strict: the fields the app needs, non-null where the app needs them, real enums, `Instant`
and the like.

```kotlin
// the domain model: no DTO in sight
data class User(val id: String, val name: String, val role: Role)

// UserMapper.kt, in the networking layer
internal fun UserDto.toDomain(): User? {
    val id = id ?: return null          // unusable without an id: drop it
    return User(
        id = id,
        name = name.orEmpty(),          // a default, never a crash
        role = Role.fromApi(status),    // unknown -> Role.Unknown
    )
}

internal fun List<UserDto>?.toDomain(): List<User> = orEmpty().mapNotNull { it.toDomain() }
```

- The mapper is where the optional fields are dealt with: a **default** for what can be missing, a **fallback** for an
  unknown value, and **dropping the item** (returning `null`) for what is unusable without a field (no id). It never
  throws.
- The mapper is a plain function `XDto.toDomain()`, unit-tested on the JVM with a DTO that has fields missing
  ([app-conventions.md](app-conventions.md)).
- Never put a DTO in a `UiState`, a `Route`, a Navigation 3 key or a `ViewModel`, and never `@Serializable`-annotate a
  domain model just to reuse it as a DTO.

## The debug kit network log

**An app that makes network calls must link its client to the library's network log**, so that every call is recorded
(method, URL, status, headers, bodies, timing) for the **Network** page of the debug pages:

```kotlin
HttpClient(OkHttp) {
    engine { addInterceptor(NetworkLogInterceptor()) }
}
```

`NetworkLogInterceptor` is from `com.lukeneedham.common.network` and does nothing in release builds. This is not
optional, even for an app that shows no debug pages; an app that shows them also adds the `NetworkPage`
([using-the-library.md](using-the-library.md#wiring-the-pages-into-your-navigation)). If the app has more than one
client, every one gets it.

## Done checklist

- [ ] Ktor client with the OkHttp engine, created once and injected; no other HTTP client
- [ ] Every network model is `@Serializable` and named `XDto`, every property nullable with a `null` default, enums as `String?`
- [ ] The `Json` is lenient (`ignoreUnknownKeys`, `isLenient`, `coerceInputValues`, `explicitNulls = false`)
- [ ] A mapper `XDto.toDomain()` for each DTO, never throwing; no DTO outside the networking layer
- [ ] Failed calls are caught and logged with `Logger.e`, not allowed to crash
- [ ] `NetworkLogInterceptor()` added to the engine of every client
