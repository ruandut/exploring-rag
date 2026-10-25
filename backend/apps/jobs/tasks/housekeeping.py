"""Cron example. Cron triggers are registered with Hatchet when the worker starts and are
visible (and manually triggerable) under the task in the Hatchet UI."""

from hatchet_sdk import Context, EmptyModel

from ..hatchet import get_hatchet

hatchet = get_hatchet()


@hatchet.task(name="nightly-housekeeping", on_crons=["0 3 * * *"])
def nightly_housekeeping(input: EmptyModel, ctx: Context) -> dict:
    # Later: delete orphaned uploads, retry failed embeddings, check LLM endpoints.
    ctx.log("Nothing to clean up yet")
    return {"cleaned": 0}
