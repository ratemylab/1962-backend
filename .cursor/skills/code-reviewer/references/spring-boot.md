# Spring Boot — Review Checklist

Use with `java.md` for language-level review. Focus on Spring idioms and common foot-guns.

## Configuration

- **Profiles** (`dev`, `prod`, etc.): secrets via env or external config; not hard-coded.
- **`@ConfigurationProperties`**: typed config vs scattered `@Value` when complexity grows.

## Beans

- **Scopes**: default singleton is fine; request/session scope only when justified and documented.
- **Circular dependencies**: resolve by design (extract interface, lazy) rather than `@Lazy` everywhere.

## Web layer

- **`@RestController`**: keep thin—delegate to services; consistent DTOs for input/output.
- **DTOs vs Entities**: never expose JPA entities directly in REST responses; map to API-facing DTOs.
- **Mapping**: use a consistent mapping approach (MapStruct or well-structured manual mapping); avoid reflection-heavy mappers in hot paths.
- **Validation**: `jakarta.validation` on request bodies; clear error response format (`@ControllerAdvice`).
- **OpenAPI/Swagger**: annotation usage is consistent, and auth/security schemes are documented.

## Data access

- **`@Transactional`**: correct boundary (service vs repository); read-only for queries when supported.
- **JPA**: N+1 and lazy-loading surprises; use fetch joins or `@EntityGraph` where appropriate.
- **Repositories**: query methods vs `@Query` documented when non-obvious.
- **Migrations (Flyway/Liquibase)**: versioned scripts are clear and ordered; avoid destructive changes without rollback strategy.
- **Migration testing**: CI validates migration paths (up and down where supported) to catch schema drift early.

## Exception handling

- **`@ControllerAdvice`**: centralize exception translation with a consistent error response format across endpoints.
- **Exception hierarchy**: custom exceptions distinguish business/domain failures from technical/infrastructure failures.
- **Stack traces**: never leak internal stack traces to clients in production responses.

## Security

- **Spring Security**: matcher order matters; least privilege on routes.
- **CSRF**: enabled for session-based browser apps; understand token strategy for APIs.

## Observability

- **Actuator**: expose only safe endpoints in production; secure sensitive endpoints.
- **Logging**: structured logging; no PII or secrets in log messages.
- **Health checks**: liveness and readiness probes are configured separately and reflect real app state.
- **Graceful shutdown**: `server.shutdown=graceful` plus a reasonable timeout for in-flight requests.
- **Resource limits**: JVM and Spring memory settings align with container/Kubernetes limits.

## Async and background tasks

- **`@Async`**: explicit executor configuration (thread pool, queue) and exception handling for async failures.
- **`@Scheduled`**: jobs are idempotent in multi-instance deployments; use distributed locking when required.

## Testing

- **`@SpringBootTest` vs slice tests** (`@WebMvcTest`, `@DataJpaTest`): use narrowest scope that proves the change.
- **Testcontainers** (if used): lifecycle and reuse patterns consistent with project.

## Performance

- **Connection pools** and timeouts aligned with deployment.
- **Caching**: eviction and key design when adding `@Cacheable`.
