from django.db import models
from chem.models import Isotopologue
from data.models import DataCollection

class XsecMeta(models.Model):
    isotopologue = models.ForeignKey(Isotopologue, on_delete=models.CASCADE)
    numin = models.FloatField()
    numax = models.FloatField()
    Tmin = models.FloatField()
    Tmax = models.FloatField()
    dnu = models.FloatField()
    data_collection = models.ForeignKey(DataCollection,
                                        on_delete=models.CASCADE)

    def __str__(self):
        return str(self.isotopologue)

    class Meta:
        db_table = 'xsec_meta'

