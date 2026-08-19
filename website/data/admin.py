from django.contrib import admin
from data.models import Link, DataType, DataSet, DataCollection, Versioning

class LinkAdmin(admin.ModelAdmin):
    list_display = ('url',)
    search_fields = ['url', 'description']
admin.site.register(Link, LinkAdmin)

class DataTypeAdmin(admin.ModelAdmin):
    pass
admin.site.register(DataType, DataTypeAdmin)

class DataSetAdmin(admin.ModelAdmin):
    search_fields = ['name']
admin.site.register(DataSet, DataSetAdmin)

class DataCollectionAdmin(admin.ModelAdmin):
    ordering = ('isotopologue',)
    list_display = ('isotopologue', 'data_set', 'data_type', 'version')
    filter_horizontal = ('link',)
    filter_vertical = ('source',)
    search_fields = ['isotopologue__ordinary_formula',
                     'isotopologue__molecule__ordinary_formula',
                     'data_set__name', 'version']

    class Media:
        css = {
            'all': ('/static/css/data_collection_admin_styles.css',)
        }
admin.site.register(DataCollection, DataCollectionAdmin)

class VersioningAdmin(admin.ModelAdmin):
    list_display = ('isotopologue', 'data_set', 'version')
    search_fields = ['isotopologue__ordinary_formula',
                     'isotopologue__molecule__ordinary_formula',
                     'data_set__name', 'version']
admin.site.register(Versioning, VersioningAdmin)
