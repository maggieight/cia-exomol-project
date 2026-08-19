import os
import json
from django.db import models
from chem.models import Isotopologue
from refs.models import Source

class Link(models.Model):
    """
    A URL to a single file (e.g. .states file) of a data collection
    (e.g. a "linelist") of a data set (e.g. BT2).

    """

    url = models.CharField(max_length=200)
    size = models.BigIntegerField(blank=True, null=True)
    description = models.TextField()
    local_file = models.BooleanField()


    class Meta:
        db_table = 'data_link'

    def __str__(self):
        return self.url

    def display(self):
        if self.local_file:
            return os.path.basename(self.url)
        return self.url
 
    def as_dict(self, relative_urls=False):
        d = {}
        if not relative_urls:
            d['url'] = 'exomol.com' + self.url
        else:
            d['url'] = self.url
        if self.size:
            d['size'] = self.size
        d['description'] = self.description

        return d

    def serialize(self):
        d = {}
        if self.local_file:
            d['url'] = 'https://exomol.com' + self.url
        else:
            d['url'] = self.url
        if self.size:
            d['size_bytes'] = self.size
        d['description'] = self.description
        return d

class DataType(models.Model):
    """
    Data are classified by 'type': 'line list', 'energy levels', etc.

    """

    name = models.CharField(max_length=64)
    type_str = models.CharField(max_length=64)
    description = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'data_type'


class DataSet(models.Model):
    """
    A DataSet is a calculation or other presentation of data concerning an
    isotopologue. DataSets are identified by names which are traditionally
    some abbreviation formed from the authors' initials, e.g. 'BT2'.

    """

    name = models.CharField(max_length=128)
    description = models.TextField()
    external = models.BooleanField(default=False)
    recommended = models.BooleanField(default=False)
    version = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'data_set'


    def serialize(self, isotopologue):
        d = {'qid': 'D{}'.format(self.pk)}
        d['name'] = self.name
        d['description'] = self.description
        d['external'] = self.external
        d['recommended'] = self.recommended
        d['def_file'] = ('https://exomol.com/db/'
                '{molec}/{iso}/{ds_name}/{iso}__{ds_name}.def'
                .format(molec=isotopologue.molecule.slug,
                iso=isotopologue.slug, ds_name=self.name)
                        )
        d['spectroscopic_model_url'] = ('https://exomol.com/models/'
                '{}/{}/{}'.format(isotopologue.molecule.slug,
                                  isotopologue.slug, self.name)
                                       )
        for dc in self.datacollection_set.all():
            d[dc.data_type.type_str] = dc.serialize()
        return d

    def json(self, isotopologue):
        return json.dumps(self.serialize(isotopologue))


class DataCollection(models.Model):
    isotopologue = models.ForeignKey(Isotopologue, on_delete=models.CASCADE)
    data_type = models.ForeignKey(DataType, on_delete=models.CASCADE)
    data_set = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    link = models.ManyToManyField(Link, db_table='data_collection__link')
    source = models.ManyToManyField(Source, db_table='data_collection__source')
    external = models.BooleanField(default=False, db_column='external')
    version = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return '%s %s - %s' % (self.isotopologue, self.data_type,
                                self.data_set)

    class Meta:
        db_table = 'data_collection'


    def serialize(self):
        d = {'qid': 'C{}'.format(self.pk)}
        d['description'] = self.data_type.description
        d['external'] = self.external
        d['sources'] = []
        for source in self.source.all():
            d['sources'].append(source.serialize())
        d['files'] = []
        for link in self.link.all():
            d['files'].append(link.serialize())
        return d


class Versioning(models.Model):
    data_set = models.ForeignKey(DataSet, on_delete=models.CASCADE)
    isotopologue = models.ForeignKey(Isotopologue, on_delete=models.CASCADE)
    zenodo_doi = models.CharField(max_length=100, blank=True)
    version = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ('-version', )

    def __str__(self):
        return (f'{self.isotopologue.ordinary_formula}: {self.data_set.name},'
                f' Version {self.version}')
