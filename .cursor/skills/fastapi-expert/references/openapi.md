# API Design - OpenAPI / Swagger (Spec-first)

## Overview

Use **OpenAPI 3** as the contract for your FastAPI services. In a **spec-first / design-first** workflow, the OpenAPI document (YAML or JSON) is the **source of truth** for endpoints, payloads, and error models. FastAPI then implements that contract and exposes interactive documentation via the built-in `/docs` (Swagger UI) and `/redoc` UIs.

When the user provides an OpenAPI spec, treat it as the contract to implement, not something to “approximate”.

## Spec-first / design-first workflow

When a user provides an **OpenAPI specification file**:

1. **Load and validate the spec**
   - Accept `.yaml`, `.yml`, or `.json`.
   - Validate the document (e.g. with `openapi-schema-validator`, `prance`, or `datamodel-code-generator`’s built-in validation).
   - Fail fast if the spec is not valid OpenAPI 3.

2. **Generate Pydantic models from schemas**
   - For each schema used in request/response bodies:
     - Generate **Pydantic V2 models** with:
       - Fields matching schema properties and types (e.g. `datetime` for `date-time`, `Decimal` for precise `number`).
       - Field constraints from the spec (`minLength`, `maxLength`, `pattern`, `minimum`, `maximum`, `enum`).
       - Optional descriptions and examples from `description`, `example`, or `x-*` vendor extensions.
     - Prefer one module per domain (e.g. `schemas/users.py`, `schemas/orders.py`) when the spec is large.

3. **Generate FastAPI routers from paths/operations**
   - For each `path` + `method` in the spec:
     - Create an `APIRouter` function with:
       - Correct HTTP method decorator (`@router.get`, `@router.post`, etc.).
       - Matching `path` (including `{path_params}`) and tags from `tags`/`x-tags`.
       - Typed parameters for path/query/header/cookie sources using Pydantic and FastAPI parameter functions (e.g. `Path`, `Query`, `Header`, `Cookie`).
       - Request body annotation using the generated Pydantic model: `payload: CreateUserRequest`.
       - Response model(s) from `responses`: `response_model=UserResponse` or `response_model=list[UserResponse]`.
       - Correct status codes (e.g. 201 for create, 204 for delete with no body).
   - Use **dependency injection** for shared concerns (auth, DB sessions, rate limiting, etc.) instead of inlining everything in handlers.

4. **Map security schemes to dependencies**
   - For `http` bearer/JWT schemes:
     - Implement a `OAuth2PasswordBearer` or custom dependency that validates tokens and returns the current user or principal.
     - Attach security requirements from the spec via dependencies on routers or endpoints.
   - For API keys (header/query):
     - Add dependencies that validate the key and raise `HTTPException(status_code=401/403)` when invalid.

5. **Stub business logic, honor contracts**
   - Handler functions should:
     - Receive validated, typed data from Pydantic models and FastAPI’s parameter parsing.
     - Return responses that match the documented `response_model` and status codes.
     - Place business logic behind services/repos so that the HTTP layer remains thin.
   - It is acceptable to initially return `HTTPException(status_code=501, detail=\"Not implemented\")` for operations that are not yet implemented, as long as they are present in the router and documented.

6. **Keep OpenAPI and implementation in sync**
   - Avoid editing the generated OpenAPI from FastAPI by hand; treat the original spec as the contract and update it when requirements change.
   - Regenerate or update Pydantic models and routers when the spec evolves.
   - Use `app.openapi()` override only when you need to inject additional metadata or merge multiple specs, not to diverge from the contract.

## Tooling suggestions

You can use these tools to accelerate a spec-first workflow (optional, but recommended):

- **`datamodel-code-generator`** – Generate Pydantic models from OpenAPI schemas.
- **`fastapi-code-generator`** or similar – Generate routers and models from an OpenAPI spec.
- **Validation libraries** – `openapi-schema-validator`, `prance`, or `speccy` (if using Node-based tooling in CI).

The `fastapi-expert` skill should:

- Prefer **clear, readable generated code** over hyper-generic scaffolding.
- Adjust generated code to match the project’s module layout (e.g. `app.api.v1`, `app.schemas`, `app.services`).

## Example: integrating a provided OpenAPI spec

Given a `openapi.yaml` describing a `/users` resource:

1. **Place the spec** under a reasonable path (e.g. `openapi/users.yaml` or `docs/openapi.yaml`).
2. **Generate models** into `app/schemas/users.py` (either manually following the spec, or via a generator).
3. **Create a router module** `app/api/users.py`:
   - Attach it under a prefix and tag that matches the spec.
   - Implement operations with correct status codes and response models.
4. **Include the router** in `app/main.py`:

```python
from fastapi import FastAPI
from app.api import users

app = FastAPI()
app.include_router(users.router, prefix=\"/api\", tags=[\"users\"])
```

5. **Verify the contract**:
   - Compare `app.openapi()` output (what FastAPI serves) with the original spec.
   - Adjust routes, models, or metadata until they match (or until deliberate extensions are documented).

## Constraints and best practices

- **Do**
  - Treat the OpenAPI document as the **single source of truth** in spec-first mode.
  - Generate or maintain Pydantic V2 models that accurately reflect the schemas.
  - Use FastAPI’s type system and dependency injection to keep handlers small and well-typed.
  - Validate that runtime OpenAPI (`/openapi.json`) matches the spec provided by the user.

- **Do not**
  - Drift away from the spec without updating it; keep the contract and implementation aligned.
  - Silently change response shapes that would break clients generated from the spec.
  - Expose undocumented error responses in production APIs (e.g. leaking stack traces).

This reference is specifically for **spec-first/design-first** workflows. For endpoint design, routing patterns, and general FastAPI structure, see `references/endpoints-routing.md`. For authentication details, see `references/authentication.md`.

