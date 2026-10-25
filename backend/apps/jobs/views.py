from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response


class DemoIndexSerializer(serializers.Serializer):
    steps = serializers.IntegerField(min_value=1, max_value=50, default=10)


@api_view(["POST"])
def start_demo_index(request):
    from .tasks.indexing import DemoIndexInput, demo_index

    data = DemoIndexSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    run = demo_index.run_no_wait(DemoIndexInput(user_id=request.user.id, **data.validated_data))
    return Response({"run_id": run.workflow_run_id}, status=202)
