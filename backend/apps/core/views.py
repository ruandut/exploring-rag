from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness of the pieces the API depends on. Used by the System Design page."""
    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = cur.fetchone()
        checks["postgres"] = "ok"
        checks["pgvector"] = row[0] if row else "missing"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a status string
        checks["postgres"] = f"error: {exc}"
    try:
        async_to_sync(get_channel_layer().send)("health.check", {"type": "noop"})
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
    return Response(checks)
