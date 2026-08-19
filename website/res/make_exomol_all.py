import os
import sys
from datetime import datetime
import urllib.request
from urllib.error import HTTPError

from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

from chem.models import Molecule
from data.models import DataCollection, DataSet

filename = 'exomol.all.new'
# A dry run doesn't get the .def file version numbers from the exomol website.
DRY_RUN = True

molecules = Molecule.objects.all()

mr = {}
for molecule in molecules:
    mr[molecule] = {}
    for iso in molecule.isotopologue_set.all():
        dcs = iso.datacollection_set.exclude(
                data_set__name__startswith='xsec').exclude(
                data_set__name__startswith='broadening').all()
        ds_pks = dcs.values_list('data_set', flat=True)
        dss = DataSet.objects.filter(pk__in=ds_pks)
        if not dss:
            print('Skipping {} which has no DataSets'.format(iso))
            continue

        # If there is one DataSet for this Isotopologue, use it:
        if len(dss) == 1:
            mr[molecule][iso] = dss[0]
            continue

        # If there is more than one, but one is recommended, use that one:
        rds = dss.filter(recommended=True)
        if len(rds) == 1:
            mr[molecule][iso] = rds[0]
            continue
        else:
            # If there is more than one recommended DataSet, but only one
            # that is not external, use the internal one:
            irds = rds.filter(external=False)
            if len(irds) == 1:
                mr[molecule][iso] = irds[0]
                continue

        # Exceptions
        if iso.ordinary_formula == '(9Be)(1H)':
            mr[molecule][iso] = DataSet.objects.get(name='Darby-Lewis')
        elif iso.ordinary_formula == '(12C)(16O)2':
            mr[molecule][iso] = DataSet.objects.get(name='Zak')
        elif iso.ordinary_formula == '(40Ca)(1H)':
            mr[molecule][iso] = DataSet.objects.get(name='MoLLIST')
        elif iso.ordinary_formula == '(24Mg)(1H)':
            mr[molecule][iso] = DataSet.objects.get(name='Yadin')
        else:
            print('I could not decide which DataSet to use for {}'.format(iso))
            print('Options are:', dss)
            sys.exit()

def get_dataset_version(iso, ds):
    url = 'http://exomol.com/db/{}/{}/{}/{}__{}.def'.format(iso.molecule.slug,
            iso.slug, ds.name, iso.slug, ds.name)
    req = urllib.request.Request(url)
    try:
        response = urllib.request.urlopen(req)
    except HTTPError as e:
        print('HTTPError {} for {}'.format(e.code, url))
        return
    content = response.read().decode('utf-8')
    lines = content.split('\n')
    line = lines[4].strip()
    #print(line)
    version = line[:8]
    return version

today = datetime.today()
version = today.strftime('%Y%m%d')
nmolecules = len(mr)
with open(filename, 'w') as fo:
    print('{:80s}# ID'.format('EXOMOL.master'), file=fo)
    print('{:80s}# Version number with format YYYYMMDD'.format(version),
                            file=fo)
    print('{:4d}'.format(nmolecules) + ' '*76 +
          '# Number of molecules in the database', file=fo)
    for molecule in mr:
        if not mr[molecule]:
            continue
        print(file=fo)
        names = []
        if molecule.names:
            names = [name.strip() for name in molecule.names.split(';')]
        print('{:4d}'.format(len(names)) + ' '*76 +
              '# Number of molecule names listed', file=fo)
        for name in names:
            print('{:80s}# Name of the molecule'.format(name), file=fo)
        print('{:80s}# Molecule chemical formula'
                            .format(molecule.ordinary_formula), file=fo)
        nisos = len(mr[molecule])
        print('{:4d}'.format(nisos) + ' '*76 +
              '# Number of isotopologues considered', file=fo)
        for iso in mr[molecule]:
            print('{:80s}# Inchi key of isotopologue'.format(iso.get_inchikey()),
                                            file=fo)
            print('{:80s}# Iso-slug'.format(iso.slug), file=fo)
            print('{:80s}# IsoFormula'.format(iso.ordinary_formula), file=fo)
            ds = mr[molecule][iso]
            print('{:80s}# Isotopologue dataset name'.format(ds.name), file=fo)

            ds_version = 'ZZZZZZZZ'
            if not DRY_RUN:
                ds_version = get_dataset_version(iso, ds) or 'XXXXXXXX'
            print('{:80s}# Version number with format YYYYMMDD'
                        .format(ds_version), file=fo)

