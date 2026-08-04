# Python — Review Checklist

Use with general review docs. Focus on idioms and tooling common in Python 3.11+ codebases.

## Style and tooling

- Prefer **formatter/linter output** (e.g. Ruff, Black) over subjective style debates in review.
- **Imports**: stdlib → third party → local; avoid circular imports; no unused imports.
- **Public APIs**: type hints on exported functions/classes when the project uses typing.

## Types and contracts

- **`Optional` / `| None`**: explicit when `None` is valid; avoid bare `Optional` misuse.
- **Protocols / ABCs**: prefer structural typing where it fits the codebase.
- **Overuse of `Any`**: flag when it hides real types.

## Exceptions

- Catch **specific** exception types; avoid bare `except:` or `except Exception:` without re-raise or logging.
- Preserve **exception chains** (`raise ... from err`) when wrapping errors.

## Async and concurrency

- **Async**: no blocking I/O in `async def` (use async drivers or `asyncio.to_thread` when appropriate).
- **Threads / multiprocessing**: clear ownership and lifecycle; watch shared mutable state.

## Packaging and dependencies

- **Pins / lockfiles**: consistent with project (`requirements.txt`, `uv.lock`, Poetry, etc.).
- **Secrets**: not in code or committed env files; use env or secret managers.

## Testing

- **pytest**: fixtures scoped appropriately; avoid hidden global state in tests.
- **Mocks**: mock boundaries (I/O, external APIs), not internals of the unit under test unless necessary.

## Security

- Avoid **`eval`**, **`exec`**, and unsafe **YAML**/`pickle` on untrusted data.
- **Subprocess**: pass arguments as lists, not shell strings, when invoking commands.

## Performance (when relevant)

- **Hot paths**: prefer comprehensions over repeated append where readability allows.
- **I/O**: streaming for large files; don’t load entire huge datasets into memory without need.
