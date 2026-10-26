"""Re-judge finished runs with the new verdict rule.

Before: a run passed when no case *errored* and every boundary held, so a run with no boundaries
said "Passed" while its cases showed "Failed" chips (scored below the threshold). Now a run
passes only when every case passed and every boundary held, and `failed_cases` counts the same
cases the chips call failed. The boundaries stored in each summary are reused as-is.
"""

from django.db import migrations


def recompute(apps, schema_editor):
    BenchmarkRun = apps.get_model("benchmarks", "BenchmarkRun")
    for run in BenchmarkRun.objects.exclude(status="running"):
        results = list(run.results.all())
        if not results:
            continue
        failed = sum(1 for r in results if not r.passed)
        errored = sum(1 for r in results if r.status == "failed")
        boundaries = (run.summary or {}).get("boundaries", [])
        passed = not failed and all(b.get("passed") is not False for b in boundaries)
        run.summary = {
            **(run.summary or {}),
            "failed_cases": failed,
            "errored_cases": errored,
            "passed_cases": len(results) - failed,
        }
        run.status = "passed" if passed else "failed"
        run.save(update_fields=["summary", "status"])


class Migration(migrations.Migration):
    dependencies = [
        ("benchmarks", "0003_case_timings"),
    ]

    operations = [migrations.RunPython(recompute, migrations.RunPython.noop)]
