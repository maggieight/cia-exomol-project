import os
import sys
from conf import exomol3_root

sys.path.append(exomol3_root)
os.environ['DJANGO_SETTINGS_MODULE'] = 'exomol3.settings'

# Prepare the Django models
import django
django.setup()

import re
from refs.models import Source, SourceType
from data.models import DataCollection
from spectroscopic_model.models import SpectroscopicModel

def source_matches(source1, source2):
    if source1.refID is None or source2.refID is None:
        return False
    if source1.refID == '' or source2.refID == '':
        return False
    if source1.refID.split('.')[0] == source2.refID.split('.')[0]:
        return True
    return False

sources = Source.objects.all()

dupes = {}
for source in sources:
    for seen_source in dupes.keys():
        if source_matches(source, seen_source):
            dupes[seen_source].append(source)
            break
    else:
        dupes[source] = [source]
print(len(dupes))
print(len(sources))

#import sys; sys.exit()

for sources in dupes.values():
    if len(sources) < 2:
        continue
    tags = set([tag for source in sources[1:] for tag in source.tags.names()])
    for tag in tags:
        sources[0].tags.add(tag)
    #print('UPDATE data_collection__source set source_id =', sources[0].id,'WHERE source_id in (',', '.join([str(source.id) for source in sources[1:]]),');')
    #print('UPDATE spectroscopic_model__source set source_id =', sources[0].id,'WHERE source_id in (',', '.join([str(source.id) for source in sources[1:]]),');')
    for source in sources[1:]:
        source.delete()

    print(sources[0].refID, sources[0].tags.names())
