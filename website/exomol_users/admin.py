from django.contrib import admin
from .models import ExoMolUserProfile, ExoMolGroupMemberProfile

class ExoMolUserProfileAdmin(admin.ModelAdmin):
    pass
admin.site.register(ExoMolUserProfile, ExoMolUserProfileAdmin)

class ExoMolGroupMemberProfileAdmin(admin.ModelAdmin):
    pass
admin.site.register(ExoMolGroupMemberProfile, ExoMolGroupMemberProfileAdmin)
