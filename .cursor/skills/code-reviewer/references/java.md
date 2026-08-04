# Java — Review Checklist

Use with general review docs. Adapt to the project’s Java version and style (e.g. records vs POJOs).

## Structure and APIs

- **Packages**: clear layering (e.g. domain vs infrastructure); no cycles.
- **Visibility**: minimize `public` surface; prefer package-private where possible.

## Null safety

- **`Optional`**: use for absent values in returns; avoid `Optional` for fields if the team prefers nullable annotations + validation.
- **NPE risks**: validate inputs at boundaries; don’t chain calls on possibly-null without checks.

## Exceptions

- **Checked vs unchecked**: follow project conventions; don’t swallow exceptions silently.
- **Wrapping**: preserve cause (`initCause` / constructor) when rethrowing.

## Concurrency

- **Thread safety**: document if types are safe for concurrent use; watch static mutable state.
- **Locks**: prefer `java.util.concurrent` over low-level `synchronized` when complexity grows.

## Resources

- **Try-with-resources** for `AutoCloseable`; ensure pools and clients are closed on shutdown.

## Collections and streams

- **Streams**: readability vs performance; avoid multiple passes when one suffices.
- **Mutability**: prefer immutable collections exposed from APIs when appropriate.

## Serialization

- **JSON/XML**: consistent annotations; versioning for persisted or wire formats.
- **Deserialization**: don’t enable unsafe defaults on untrusted input.

## Build and dependencies

- **Maven/Gradle**: consistent BOM or version management; no duplicate conflicting libraries.
- **Security**: keep dependencies updated; watch for known CVEs on critical libs.

## Testing

- **JUnit**: clear test names; one logical assertion focus per test when possible.
- **Mocks**: Mockito (or project standard); verify only relevant interactions.
