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

def build_dict(filename):
    ja = {}
    with open(filename) as fi:
        for line in fi.readlines():
            try:
                k, v = [e.strip() for e in line.split(' = ')]
            except ValueError:
                print('malformed line: ', line)
            ja[k] = v
    return ja

ja = {}
ja.update(build_dict('journal_abbrevs.txt'))
ja.update(build_dict('journal_abbrevs2.txt'))

journal_titles = list(ja.values())

sources = Source.objects.all()
unknown_jas = set()
for source in sources:
    if (source.journal is not None and
        source.journal not in journal_titles and
        source.journal not in ja.keys()):
        unknown_jas.add(source.journal)
    if source.journal in ja.keys():
        source.journal = ja[source.journal]
        source.save()

for j in sorted(unknown_jas):
    print(j)

print(len(unknown_jas))

        
    

