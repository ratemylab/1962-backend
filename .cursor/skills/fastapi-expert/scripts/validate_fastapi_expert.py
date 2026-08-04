import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Literal, Optional


Status = Literal["pass", "fail", "warn", "skip"]
Severity = Literal["error", "warning", "info"]


@dataclass
class CheckResult:
    id: str
    description: str
    status: Status
    severity: Severity = "error"
    details: Optional[str] = None


@dataclass
class ValidationContext:
    project_root: Path
    app_root: Optional[Path]
    py_files: List[Path]
    db_dir: Optional[Path]


def discover_project(project_root: Path) -> ValidationContext:
    app_root = None
    for candidate in ("app", "src/app"):
        candidate_path = project_root / candidate
        if candidate_path.is_dir():
            app_root = candidate_path
            break

    search_root = app_root or project_root
    py_files = [p for p in search_root.rglob("*.py") if "venv" not in p.parts and ".venv" not in p.parts]

    db_dir = project_root / "db"
    if not db_dir.is_dir():
        db_dir = None

    return ValidationContext(
        project_root=project_root,
        app_root=app_root,
        py_files=py_files,
        db_dir=db_dir,
    )


def _iter_file_texts(ctx: ValidationContext) -> Iterable[tuple[Path, str]]:
    for path in ctx.py_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        yield path, text


# --- Individual checks ---


def check_type_hints_and_async(ctx: ValidationContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    endpoint_funcs = 0
    missing_hints = 0
    sync_endpoints = 0

    decorator_pattern = re.compile(r"@(app|router)\.(get|post|put|delete|patch|options|head)\b")

    for path, text in _iter_file_texts(ctx):
        if "fastapi" not in text and "APIRouter" not in text:
            continue

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue

            has_fastapi_decorator = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and isinstance(d.func.value, ast.Name)
                and d.func.value.id in {"app", "router"}
                for d in node.decorator_list
            )

            if not has_fastapi_decorator and not any(
                isinstance(d, ast.Name) and d.id.startswith("router_")
                for d in node.decorator_list
            ):
                # Fallback: only lines *above* the def (decorators), not the whole body — avoids
                # false positives when nested functions inside a factory use @router.*.
                start = getattr(node, "lineno", 0)
                if start < 1:
                    continue
                head = "\n".join(text.splitlines()[max(0, start - 40) : start - 1])
                if not decorator_pattern.search(head):
                    continue

            endpoint_funcs += 1

            # async check
            if not isinstance(node, ast.AsyncFunctionDef):
                sync_endpoints += 1

            # type hints check: params and returns
            has_param_annotations = all(
                (not isinstance(arg, ast.arg)) or (arg.annotation is not None)
                for arg in node.args.args
            )
            has_return_annotation = node.returns is not None

            if not (has_param_annotations and has_return_annotation):
                missing_hints += 1

    if endpoint_funcs == 0:
        results.append(
            CheckResult(
                id="type-hints-async",
                description="FastAPI endpoints should be async and fully type-annotated",
                status="skip",
                severity="info",
                details="No FastAPI-style endpoints were detected.",
            )
        )
        return results

    if sync_endpoints == 0 and missing_hints == 0:
        results.append(
            CheckResult(
                id="type-hints-async",
                description="FastAPI endpoints are async and fully type-annotated",
                status="pass",
                severity="info",
            )
        )
    else:
        problems: list[str] = []
        if sync_endpoints:
            problems.append(f"{sync_endpoints} endpoint(s) are not async")
        if missing_hints:
            problems.append(f"{missing_hints} endpoint(s) are missing type hints")

        results.append(
            CheckResult(
                id="type-hints-async",
                description="FastAPI endpoints must be async and fully type-annotated",
                status="fail",
                severity="error",
                details="; ".join(problems),
            )
        )

    return results


def check_pydantic_v2(ctx: ValidationContext) -> List[CheckResult]:
    v2_markers = 0
    v1_markers = 0

    for _, text in _iter_file_texts(ctx):
        if "BaseModel" not in text and "pydantic" not in text:
            continue

        if any(k in text for k in ("field_validator", "model_validator", "model_config")):
            v2_markers += 1
        if "@validator" in text or "class Config(" in text or "class Config:" in text:
            v1_markers += 1

    if v2_markers == 0 and v1_markers == 0:
        return [
            CheckResult(
                id="pydantic-v2",
                description="Pydantic V2 usage for schemas",
                status="skip",
                severity="info",
                details="No Pydantic models detected.",
            )
        ]

    if v2_markers > 0 and v1_markers == 0:
        return [
            CheckResult(
                id="pydantic-v2",
                description="Pydantic V2 APIs are used (no V1-only patterns found)",
                status="pass",
                severity="info",
            )
        ]

    return [
        CheckResult(
            id="pydantic-v2",
            description="Pydantic V2 must be used instead of V1-only APIs",
            status="fail",
            severity="error",
            details="V1-only constructs (@validator / class Config) detected without consistent V2 markers.",
        )
    ]


def check_annotated_dependencies(ctx: ValidationContext) -> List[CheckResult]:
    annotated_occurrences = 0
    depends_only = 0

    for _, text in _iter_file_texts(ctx):
        if "Depends(" not in text:
            continue
        if "Annotated[" in text:
            annotated_occurrences += 1
        if "Annotated[" not in text:
            depends_only += 1

    if annotated_occurrences == 0 and depends_only == 0:
        return [
            CheckResult(
                id="annotated-deps",
                description="Annotated[...] should be used for dependency injection",
                status="skip",
                severity="info",
                details="No FastAPI dependencies detected.",
            )
        ]

    if annotated_occurrences > 0:
        return [
            CheckResult(
                id="annotated-deps",
                description="Annotated[...] is used for FastAPI dependencies",
                status="pass",
                severity="info",
            )
        ]

    return [
        CheckResult(
            id="annotated-deps",
            description="Use Annotated[...] pattern for FastAPI dependencies",
            status="warn",
            severity="warning",
            details="Only legacy Depends(...) style dependencies were found.",
        )
    ]


def check_cors_and_settings(ctx: ValidationContext) -> List[CheckResult]:
    cors_found = False
    settings_used_for_cors = False

    for path, text in _iter_file_texts(ctx):
        if "CORSMiddleware" not in text:
            continue
        cors_found = True
        if "settings" in text or "BaseSettings" in text or "pydantic_settings" in text:
            settings_used_for_cors = True

    if not cors_found:
        return [
            CheckResult(
                id="cors",
                description="CORS should be configured explicitly via CORSMiddleware with origins from settings",
                status="warn",
                severity="warning",
                details="No CORSMiddleware configuration found.",
            )
        ]

    if settings_used_for_cors:
        return [
            CheckResult(
                id="cors",
                description="CORS is configured with settings-based origins",
                status="pass",
                severity="info",
            )
        ]

    return [
        CheckResult(
            id="cors",
            description="CORS is configured but may not be driven by settings",
            status="warn",
            severity="warning",
            details="CORSMiddleware found but no obvious settings-based origins detected.",
        )
    ]


def check_pydantic_settings(ctx: ValidationContext) -> List[CheckResult]:
    base_settings_found = False
    suspicious_hardcoded = 0

    url_like = re.compile(r"https?://")

    for path, text in _iter_file_texts(ctx):
        if "BaseSettings" in text or "pydantic_settings" in text:
            base_settings_found = True

        # Settings and OTel middleware: field names and exporter URLs are not ad-hoc hardcoding.
        path_str = str(path).replace("\\", "/")
        skip_secret_url_heuristic = (
            "instrumentation.py" in path_str or "core/config.py" in path_str
        )

        if not skip_secret_url_heuristic and any(
            k in text.lower() for k in ("password", "secret", "token", "api_key", "apikey")
        ):
            for match in re.finditer(r"['\"][^'\"]+['\"]", text):
                raw = match.group(0)
                inner = raw[1:-1]
                if len(inner) < 24:
                    continue
                # Skip natural-language user messages, multiline fragments, and format placeholders.
                if (
                    "\n" in inner
                    or (" " in inner and not inner.startswith("eyJ"))
                    or "{" in inner
                ):
                    continue
                if any(x in raw.lower() for x in ("password", "secret", "token", "api_key", "apikey")):
                    suspicious_hardcoded += 1
                    break

        if not skip_secret_url_heuristic and url_like.search(text):
            suspicious_hardcoded += 1

    results: List[CheckResult] = []

    if base_settings_found:
        results.append(
            CheckResult(
                id="pydantic-settings",
                description="Configuration uses pydantic-settings/BaseSettings",
                status="pass",
                severity="info",
            )
        )
    else:
        results.append(
            CheckResult(
                id="pydantic-settings",
                description="Configuration should rely on pydantic-settings/BaseSettings",
                status="warn",
                severity="warning",
                details="No BaseSettings/pydantic-settings usage detected.",
            )
        )

    if suspicious_hardcoded:
        results.append(
            CheckResult(
                id="hardcoded-config",
                description="Potential hardcoded secrets or URLs detected",
                status="warn",
                severity="warning",
                details=f"{suspicious_hardcoded} occurrence(s) of suspicious string literals that may represent config.",
            )
        )

    return results


def check_health_and_ready(ctx: ValidationContext) -> List[CheckResult]:
    health_found = False
    ready_found = False

    for _, text in _iter_file_texts(ctx):
        if '"/health"' in text or "'/health'" in text:
            health_found = True
        if '"/ready"' in text or "'/ready'" in text:
            ready_found = True

    results: List[CheckResult] = []

    if health_found:
        results.append(
            CheckResult(
                id="health-endpoint",
                description="Health endpoint (/health) exists",
                status="pass",
                severity="info",
            )
        )
    else:
        results.append(
            CheckResult(
                id="health-endpoint",
                description="Health endpoint (/health) should be implemented",
                status="fail",
                severity="error",
                details="No /health endpoint detected.",
            )
        )

    if ready_found:
        results.append(
            CheckResult(
                id="ready-endpoint",
                description="Ready endpoint (/ready) exists",
                status="pass",
                severity="info",
            )
        )
    else:
        results.append(
            CheckResult(
                id="ready-endpoint",
                description="Ready endpoint (/ready) is recommended when DB is used",
                status="warn",
                severity="warning",
                details="No /ready endpoint detected.",
            )
        )

    return results


def check_global_error_handler(ctx: ValidationContext) -> List[CheckResult]:
    handler_found = False
    structured_detail = False

    for _, text in _iter_file_texts(ctx):
        if "exception_handler(" in text:
            handler_found = True
            if '"detail"' in text or "'detail'" in text:
                structured_detail = True

    if not handler_found:
        return [
            CheckResult(
                id="global-error-handler",
                description="Global exception handler should be registered",
                status="warn",
                severity="warning",
                details="No app.exception_handler usage detected.",
            )
        ]

    if structured_detail:
        return [
            CheckResult(
                id="global-error-handler",
                description="Global exception handler appears to return structured error responses",
                status="pass",
                severity="info",
            )
        ]

    return [
        CheckResult(
            id="global-error-handler",
            description="Global exception handler found but response structure is unclear",
            status="warn",
            severity="warning",
        )
    ]


def check_alembic_and_models(ctx: ValidationContext) -> List[CheckResult]:
    """Expect Alembic revisions under migrations/versions/ when SQLAlchemy models exist."""
    results: List[CheckResult] = []
    models_found = False

    for _, text in _iter_file_texts(ctx):
        if "from sqlalchemy" in text and "import Column" in text:
            models_found = True
            break

    project_root = ctx.project_root
    versions_dir = project_root / "migrations" / "versions"
    alembic_revisions: List[Path] = []
    if versions_dir.is_dir():
        alembic_revisions = [p for p in versions_dir.glob("*.py") if p.name != "__init__.py"]

    if not models_found and not alembic_revisions:
        results.append(
            CheckResult(
                id="alembic-migrations",
                description="Alembic migrations should exist when using database-backed APIs",
                status="skip",
                severity="info",
                details="No SQLAlchemy models or Alembic revision files detected.",
            )
        )
        return results

    if models_found and not alembic_revisions:
        results.append(
            CheckResult(
                id="alembic-migrations",
                description="Database-backed APIs must have Alembic revision files under migrations/versions/",
                status="fail",
                severity="error",
                details="SQLAlchemy models detected but no migrations/versions/*.py revisions found.",
            )
        )
        return results

    if alembic_revisions:
        results.append(
            CheckResult(
                id="alembic-migrations",
                description="Alembic migrations detected under migrations/versions/",
                status="pass",
                severity="info",
                details=f"{len(alembic_revisions)} revision file(s) found.",
            )
        )

    return results


def check_output_templates_presence(ctx: ValidationContext) -> List[CheckResult]:
    schema_like = False
    router_like = False
    crud_like = False

    for path, text in _iter_file_texts(ctx):
        name = path.name
        parent_s = str(path.parent)
        if "BaseModel" in text and (
            "schema" in name or "schemas" in parent_s or parent_s.rstrip("/").endswith("schema")
        ):
            schema_like = True
        if "APIRouter" in text or "router = APIRouter" in text:
            router_like = True
        if "crud" in name or "crud" in str(path.parent):
            if "def " in text and ("get_" in text or "create_" in text or "update_" in text):
                crud_like = True

    results: List[CheckResult] = []

    results.append(
        CheckResult(
            id="output-schemas",
            description="Schema module(s) for Pydantic models",
            status="pass" if schema_like else "warn",
            severity="info" if schema_like else "warning",
            details=None if schema_like else "No obvious schemas.* module with BaseModel classes was found.",
        )
    )

    results.append(
        CheckResult(
            id="output-routers",
            description="Router module(s) using APIRouter",
            status="pass" if router_like else "warn",
            severity="info" if router_like else "warning",
            details=None if router_like else "No APIRouter-based router modules were detected.",
        )
    )

    results.append(
        CheckResult(
            id="output-crud",
            description="CRUD module(s) for database access",
            status="pass" if crud_like else "warn",
            severity="info" if crud_like else "warning",
            details=None if crud_like else "No obvious crud.py or CRUD package with DB helpers was found.",
        )
    )

    return results


def run_all_checks(ctx: ValidationContext) -> List[CheckResult]:
    checks: List[Callable[[ValidationContext], List[CheckResult]]] = [
        check_type_hints_and_async,
        check_pydantic_v2,
        check_annotated_dependencies,
        check_cors_and_settings,
        check_pydantic_settings,
        check_health_and_ready,
        check_global_error_handler,
        check_alembic_and_models,
        check_output_templates_presence,
    ]

    results: List[CheckResult] = []
    for fn in checks:
        results.extend(fn(ctx))
    return results


def print_report(results: List[CheckResult], as_json: bool) -> int:
    if as_json:
        payload = [
            {
                "id": r.id,
                "description": r.description,
                "status": r.status,
                "severity": r.severity,
                "details": r.details,
            }
            for r in results
        ]
        print(json.dumps(payload, indent=2))
    else:
        grouped: dict[Status, list[CheckResult]] = {"pass": [], "fail": [], "warn": [], "skip": []}
        for r in results:
            grouped[r.status].append(r)

        summary = ", ".join(f"{k.upper()} {len(v)}" for k, v in grouped.items())
        print(f"[fastapi-expert] Validation summary: {summary}")
        for status in ("fail", "warn", "skip", "pass"):
            bucket = grouped[status]  # type: ignore[index]
            if not bucket:
                continue
            print(f"\n{status.upper()}:")
            for r in bucket:
                line = f"- {r.id}: {r.description}"
                if r.details:
                    line += f" ({r.details})"
                print(line)

    has_failures = any(r.status == "fail" and r.severity == "error" for r in results)
    return 1 if has_failures else 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a FastAPI project against the fastapi-expert skill requirements."
    )
    parser.add_argument(
        "--project-path",
        required=True,
        help="Path to the FastAPI project to validate (e.g. . or ../my-app).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Treat warnings as failures when determining the exit code.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_path).resolve()

    if not project_root.exists() or not project_root.is_dir():
        print(f"Project path does not exist or is not a directory: {project_root}", file=sys.stderr)
        return 1

    ctx = discover_project(project_root)
    results = run_all_checks(ctx)

    exit_code = print_report(results, as_json=args.json)

    if args.fail_on_warn and exit_code == 0:
        if any(r.status in {"warn", "fail"} for r in results):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

