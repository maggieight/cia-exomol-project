import os
import sys
import json

from pyvalem.formula import Formula


iso_slug = sys.argv[1]
dataset_name = sys.argv[2]
use_existing_def_file = len(sys.argv) > 3 and sys.argv[3] == 'def'

from conf import exomol3_root
sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()
from django.conf import settings

from chem.models import Isotopologue
from data.models import DataType, DataSet, DataCollection, Versioning


isotopologue = Isotopologue.objects.get(slug=iso_slug)
dataset = DataSet.objects.get(name=dataset_name)

print(isotopologue, dataset)

def get_dataset_path():
    return os.path.join(settings.DATA_DIR,
                        isotopologue.molecule.slug,
                        iso_slug,
                        dataset_name)

def read_existing_def_file():
    dataset_path = get_dataset_path()
    def_name = f'{iso_slug}__{dataset_name}.def'
    existing_def_path = os.path.join(dataset_path, def_name)
    if not os.path.exists(existing_def_path):
        print(f"Can't find existing def file at {existing_def_path}")
        sys.exit(1)
    edd = {}
    with open(existing_def_path) as fi:
        for line in fi.readlines():
            fields = line.split('#')
            assert len(fields) == 2
            edd[fields[1].strip()] = fields[0].strip()
    return edd


edd = read_existing_def_file() if use_existing_def_file else {}

def get_json_path():
    dataset_path = get_dataset_path()
    json_name = f'{iso_slug}__{dataset_name}.json'
    json_path = os.path.join(dataset_path, json_name)
    return json_path

def read_existing_json_file():
    json_path = get_json_path()
    try:
        with open(json_path) as fi:
            return json.loads(fi.read())
    except FileNotFoundError:
        return {}

def write_json_file(dd):
    json_path = get_json_path()
    print(f'Writing JSON metadata to {json_path}.')
    with open(json_path, 'w') as fo:
        fo.write(json.dumps(dd, indent=2))


def set_dd_if_in_edd(dd, dd_key, edd, edd_key, vtype=str, units=None):
    if not use_existing_def_file:
        return
    if edd_key in edd:
        if units:
            dd[dd_key] = {'value': vtype(edd[edd_key]), 'units': units}
        else:
            if vtype is bool:
                dd[dd_key] = bool(int(edd[edd_key]))
            else:
                dd[dd_key] = vtype(edd[edd_key])
    else:
        print(f'{edd_key} not found in existing .def file')


def update_dd_with_serialized_object(dd, dtype_str):
    dt = DataType.objects.get(type_str=dtype_str)
    dc = DataCollection.objects.get(isotopologue=isotopologue,
                                    data_set=dataset, data_type=dt)
    dd[dtype_str].update(dc.serialize())



dd = read_existing_json_file()
if not dd:
    print('Starting new, empty json metadata file')

dd['isotopologue'] = isotopologue.ordinary_formula
dd['molecule'] = isotopologue.molecule.ordinary_formula
dd['iso_slug'] = iso_slug
if isotopologue.inchi:
    dd['inchi'] = isotopologue.inchi 
if isotopologue.inchikey:
    dd['inchikey'] = isotopologue.inchikey

fiso = Formula(isotopologue.ordinary_formula)
# TODO isotope mass numbers
# isotopes

dd['total_mass'] = {'value': fiso.rmm, 'units': 'Da'}

set_dd_if_in_edd(dd, 'symmetry_group', edd, 'Symmetry group')

# irreps

dd['dataset_name'] = dataset_name

set_dd_if_in_edd(dd, 'dataset_version', edd, 'Version number with format YYYYMMDD', int)

try:
    zenodo_doi = Versioning.objects.get(data_set=dataset, isotopologue=isotopologue)
    dd['data-doi'] = zenodo_doi.zenodo_doi
except Versioning.DoesNotExist:
    print('No Versioning object found')
    pass

# source

dd['recommended'] = dataset.recommended

##### energylevels #####
if 'energylevels' not in dd.keys():
    dd['energylevels'] = {}
dd['energylevels']['file_extension'] = 'states'
set_dd_if_in_edd(dd['energylevels'], 'nstates', edd, 'No. of states in .states file', int)
set_dd_if_in_edd(dd['energylevels'], 'Emax', edd, 'Maximum wavenumber (in cm-1)', float, units='cm-1')

set_dd_if_in_edd(dd['energylevels'], 'uncertainties_available', edd, 'Uncertainty availability (1=yes, 0=no)', bool)

set_dd_if_in_edd(dd['energylevels'], 'lifetime_available', edd, 'Lifetime availability (1=yes, 0=no)', bool)
set_dd_if_in_edd(dd['energylevels'], 'lande_g_available', edd, 'Lande g-factor availability (1=yes, 0=no)', bool)




##### linelist #####
if 'linelist' not in dd.keys():
    dd['linelist'] = {}
dd['linelist']['file_extension'] = 'trans'

set_dd_if_in_edd(dd['linelist'], 'ntrans', edd, 'Total number of transitions', int)
set_dd_if_in_edd(dd['linelist'], 'ntrans_files', edd, 'No. of transition files', int)
set_dd_if_in_edd(dd['linelist'], 'numax', edd, 'Higher energy with complete set of transitions (in cm-1)', float, units='cm-1')

update_dd_with_serialized_object(dd, 'linelist')


##### partitionfunction #####
if 'partitionfunction' not in dd.keys():
    dd['partitionfunction'] = {}
dd['partitionfunction']['file_extension'] = 'pf'
set_dd_if_in_edd(dd['partitionfunction'], 'QTmax', edd, 'Maximum temperature of partition function', float, units='K')
set_dd_if_in_edd(dd['partitionfunction'], 'QdT', edd, 'Step size of temperature', float, units='K')

update_dd_with_serialized_object(dd, 'partitionfunction')


write_json_file(dd)
