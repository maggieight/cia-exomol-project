from django.urls import path
import exomol_users.views

urlpatterns = [
    path('update', exomol_users.views.update_profile),
]
