from django.urls import include, path

urlpatterns = [
    path("cia/", include(("cia.urls", "cia"), namespace="cia")),
]
