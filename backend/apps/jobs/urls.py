from django.urls import path

from . import views

urlpatterns = [path("demo-index/", views.start_demo_index, name="demo_index")]
