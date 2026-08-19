from django.contrib import admin
from spectroscopic_model.models import SpectroscopicModel

class SpectroscopicModelAdmin(admin.ModelAdmin):
    ordering = ('isotopologue',)
    list_display = ('isotopologue',)
    filter_horizontal = ('link',)
    filter_vertical = ('source',)
admin.site.register(SpectroscopicModel, SpectroscopicModelAdmin)
