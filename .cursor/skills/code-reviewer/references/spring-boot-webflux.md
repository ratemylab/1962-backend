# Spring Boot WebFlux — Review Checklist

Use with `java.md` and `spring-boot.md` for reactive Spring applications.

## Reactive execution model

- **Blocking calls**: do not block in reactive chains (`Thread.sleep`, blocking JDBC, synchronous HTTP clients, blocking filesystem access).
- **Scheduler boundaries**: when blocking work is unavoidable, isolate it explicitly and document why.

## Data access and integration

- **Reactive stack consistency**: prefer R2DBC/reactive clients end-to-end; mixing imperative repositories in request paths is a red flag.
- **Timeouts and retries**: external calls have explicit timeout/retry policies to prevent stalled pipelines.

## Backpressure and resilience

- **Backpressure**: operators and downstream integration handle slower consumers without unbounded buffering.
- **Demand control**: stream producers respect consumer demand and do not overwhelm downstream services.

## Error handling and observability

- **Reactive error paths**: domain-specific error mapping is explicit (`onError...` patterns) and consistent with API contracts.
- **Diagnostics**: logging/metrics capture reactive failures and latency without relying on stack-trace leaks to clients.
