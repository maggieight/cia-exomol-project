from django.contrib import admin
from xsec.models import XsecMeta

class XsecMetaAdmin(admin.ModelAdmin):
    pass
admin.site.register(XsecMeta, XsecMetaAdmin)
