# Spring Boot — Common Anti-Patterns

Use with `java.md` and `spring-boot.md` when reviewing service wiring and transaction correctness.

## Circular dependencies

- **Why it matters**: tightly coupled beans are harder to test, reason about, and refactor.
- **What to look for**: `BeanCurrentlyInCreationException`, bidirectional service dependencies, or repeated `@Lazy` to break cycles.
- **Preferred fix**: extract interfaces/use-cases, introduce orchestration layer, or split responsibilities to remove cycles by design.

## Over-use of `@Lazy`

- **Why it matters**: `@Lazy` can hide architecture issues and delay failure to runtime paths.
- **What to look for**: broad or default `@Lazy` usage across many services.
- **Preferred fix**: use eager wiring by default; keep `@Lazy` as a narrow, justified exception.

## Missing transaction boundaries

- **Why it matters**: multi-step updates can partially commit on failure.
- **What to look for**: service methods that perform multiple repository operations without `@Transactional`.
- **Preferred fix**: define transaction boundaries at the service layer for related operations.

## Incorrect `@Transactional` propagation

- **Why it matters**: wrong propagation can break atomicity, create unexpected nested behavior, or commit too early.
- **What to look for**: indiscriminate `REQUIRES_NEW`, misunderstanding of `MANDATORY`/`SUPPORTS`, and cross-service calls with unclear transaction ownership.
- **Preferred fix**: keep default propagation unless there is a concrete business need; document exceptions and add tests for rollback behavior.
