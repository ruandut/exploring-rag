"""Architecture guard: Django apps may only import from the apps they're allowed to depend on.

Domain apps are layered (providers / library → rag → agents → chat; scoring / evals →
benchmarks). A lower layer never imports a higher one, which keeps the dependency graph acyclic
and each app replaceable.
Cross-app calls go through the other app's services.py / selectors.py, never its models
directly — that part is a code-review rule, this test enforces the layering.

If this test fails, don't just add the import here: ask whether the code belongs in a
different app, or whether the lower app should emit a Hatchet event / signal instead.
"""

import ast
from pathlib import Path

APPS_DIR = Path(__file__).resolve().parent.parent

PLATFORM = {"core", "accounts", "realtime", "jobs"}

ALLOWED_DEPENDENCIES: dict[str, set[str]] = {
    # platform
    "core": set(),
    "accounts": {"core"},
    "realtime": {"core"},
    "jobs": {"core", "realtime"},
    # domain — each may also use any platform app
    "providers": PLATFORM,
    "library": PLATFORM,
    "rag": PLATFORM | {"providers", "library"},
    "agents": PLATFORM | {"providers", "library", "rag"},
    # chat → rag: a conversation references the embedding it searches (spec 0010).
    "chat": PLATFORM | {"providers", "agents", "rag"},
    # Benchmarks, split by responsibility: how to score / what to test / running tests.
    "scoring": PLATFORM | {"providers"},
    # evals: providers for the judge's connection, scoring for the metric vocabulary.
    "evals": PLATFORM | {"library", "providers", "scoring"},
    "benchmarks": PLATFORM | {"providers", "library", "rag", "agents", "evals", "scoring"},
}


def _imported_apps(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if len(parts) >= 2 and parts[0] == "apps":
                found.add(parts[1])
    return found


def test_every_app_is_declared():
    apps_on_disk = {p.name for p in APPS_DIR.iterdir() if (p / "apps.py").exists()}
    assert apps_on_disk == set(ALLOWED_DEPENDENCIES), (
        "Add new apps to ALLOWED_DEPENDENCIES (and INSTALLED_APPS) with their allowed imports"
    )


def test_apps_only_import_allowed_dependencies():
    violations = []
    for app, allowed in ALLOWED_DEPENDENCIES.items():
        for path in (APPS_DIR / app).rglob("*.py"):
            if path.name.startswith("test_") or "migrations" in path.parts:
                continue
            for dep in _imported_apps(path) - allowed - {app}:
                violations.append(f"{path.relative_to(APPS_DIR)} imports apps.{dep}")
    assert not violations, "Disallowed cross-app imports:\n" + "\n".join(violations)
