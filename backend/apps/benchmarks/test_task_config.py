"""Hatchet task settings that matter for slow, local models (found running a real suite)."""

from apps.benchmarks.tasks import benchmark_case, benchmark_run
from apps.providers.services import LLM_TIMEOUT_SECONDS
from apps.rag.tasks import index_document


def test_queued_cases_and_documents_are_not_cancelled_after_five_minutes():
    # Hatchet cancels a task that waits in its queue longer than its schedule timeout (5
    # minutes by default). Concurrency limits make these tasks wait, so they need longer.
    assert benchmark_case._task.schedule_timeout == "12h"
    assert benchmark_run._task.schedule_timeout == "12h"
    assert benchmark_run._task.execution_timeout == "12h"
    assert index_document._task.schedule_timeout == "6h"


def test_llm_requests_allow_slow_local_models():
    assert LLM_TIMEOUT_SECONDS >= 120
