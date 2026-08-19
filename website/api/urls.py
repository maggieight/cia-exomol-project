from django.urls import path
from django.views.generic import TemplateView
import api.views

app_name='api'
urlpatterns = [
    path('', api.views.query),
]

