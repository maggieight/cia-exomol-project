from django.db import models
from data.models import Isotopologue, DataSet, Link, Source
from mezzanine.core.fields import RichTextField

class SpectroscopicModel(models.Model):
    isotopologue = models.ForeignKey(Isotopologue, on_delete=models.CASCADE)
    data_set = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    link = models.ManyToManyField(Link, db_table='spectroscopic_model__link')
    source = models.ManyToManyField(Source,
                                    db_table='spectroscopic_model__source')
    doc = RichTextField()

    def __str__(self):
        return '{} spectroscopic model for {}'.format(self.isotopologue,
                                                      self.data_set)

    class Meta:
        db_table = 'spectroscopic_model'
        verbose_name = 'Spectroscopic Model'

