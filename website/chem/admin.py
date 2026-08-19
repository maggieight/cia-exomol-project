from django.contrib import admin
from chem.models import Molecule, Isotopologue

class MoleculeAdmin(admin.ModelAdmin):
    pass
admin.site.register(Molecule, MoleculeAdmin)

class IsotopologueAdmin(admin.ModelAdmin):
    pass
admin.site.register(Isotopologue, IsotopologueAdmin)

