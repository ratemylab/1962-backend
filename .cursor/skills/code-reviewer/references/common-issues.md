# Common Issues

## N+1 Query Problem

```
// N+1 queries — BAD: one query per row inside a loop
posts = load_all_posts()
for each post in posts:
    post.author = load_user_by_id(post.author_id)  // N extra queries

// GOOD — single query with join, OR fetch related ids then batch-load
posts = load_posts_with_authors_joined()
// or:
posts = load_all_posts()
author_ids = unique(post.author_id for post in posts)
authors_by_id = load_users_by_ids(author_ids)
attach(authors_by_id, posts)
```

## Missing Error Handling

```
// BAD — errors from network/parse can propagate unhandled or fail silently
response = http_get("/api/data")
data = parse_json(response.body)

// GOOD — check status, handle failures, log, map to domain errors
response = http_get("/api/data")
if not response.ok:
    log_error("fetch failed", status=response.status)
    raise DataFetchError("could not load data")
data = parse_json(response.body)  // handle parse errors similarly
```

## Magic Numbers/Strings

```
// BAD — literals with unclear meaning
if user.age >= 18 { ... }
schedule_after(handler, 86400000)

// GOOD — named constants
MINIMUM_AGE = 18
ONE_DAY_MS = 24 * 60 * 60 * 1000
if user.age >= MINIMUM_AGE { ... }
schedule_after(handler, ONE_DAY_MS)
```

## Deep Nesting

```
// BAD — pyramid of nesting
if user:
    if user.is_active:
        if user.has_permission:
            do_something()

// GOOD — guard clauses / early returns
if not user or not user.is_active or not user.has_permission:
    return
do_something()
```

## God Functions

```
// BAD — one function does validation, inventory, payment, email, DB, analytics
function process_order(order):
    ...

// GOOD — orchestration calls focused units
function process_order(order):
    validate_order(order)
    reserve_inventory(order)
    charge_payment(order)
    send_confirmation(order)
```

## Mutable Shared State

```
// BAD — global/singleton mutated from many call sites
shared_config.debug = true  // anywhere

// GOOD — pass configuration explicitly; prefer immutable snapshots
config = make_config(overrides)
run_with(config)
```

## Missing Null Checks

```
// BAD — assumes nested fields exist
name = user.profile.name

// GOOD — optional access + default
name = optional_chain(user, "profile", "name") ?? "Unknown"
```

## Synchronous Blocking I/O

```
// BAD — blocks a thread / event loop for disk or network
data = read_file_sync("file.txt")

// GOOD — async or background I/O appropriate to your runtime
data = await read_file_async("file.txt")
```

## Spring DI Anti-Patterns

```
// BAD — field injection hides dependencies and hurts testability
@Service
class OrderService {
    @Autowired
    private PaymentClient paymentClient;
}

// GOOD — constructor injection makes dependencies explicit
@Service
class OrderService {
    private final PaymentClient paymentClient;
    OrderService(PaymentClient paymentClient) {
        this.paymentClient = paymentClient;
    }
}
```

```
// BAD — @Autowired on multiple constructors creates ambiguity
@Component
class MyComponent {
    @Autowired MyComponent(A a) { ... }
    @Autowired MyComponent(A a, B b) { ... }
}

// GOOD — one constructor, preferably without @Autowired
@Component
class MyComponent {
    MyComponent(A a, B b) { ... }
}
```

## Spring Data/Transaction Foot-Guns

```
// BAD — repository returns full entities for read-only list views
List<UserEntity> findByStatus(Status status)

// GOOD — return projections/DTOs where full entity state is not needed
List<UserSummaryView> findByStatus(Status status)
```

```
// BAD — service spans multiple queries/writes without transaction boundary
public void transfer(...) {
    accountRepo.debit(...)
    accountRepo.credit(...)
}

// GOOD — transactional boundary at service layer
@Transactional
public void transfer(...) {
    accountRepo.debit(...)
    accountRepo.credit(...)
}
```

## Quick Reference

| Issue | Impact | Fix |
|-------|--------|-----|
| N+1 queries | Performance | Eager load or batch |
| Missing error handling | Reliability | Structured handling + logging |
| Magic numbers | Maintainability | Named constants |
| Deep nesting | Readability | Early returns |
| God functions | Testability | Single responsibility |
| Mutable shared state | Bugs | Immutable / explicit config |
| Missing null checks | Crashes | Optional access / validation |
| Sync blocking I/O | Performance | Async or pooled workers |
| Field injection | Testability / hidden deps | Constructor injection |
| Multiple `@Autowired` constructors | Wiring ambiguity | Single constructor |
| Entity-heavy repository return types | Over-fetching / coupling | Projections/DTOs |
| Missing service `@Transactional` | Partial writes / inconsistency | Define transaction boundary |
