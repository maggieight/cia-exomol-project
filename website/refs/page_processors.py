from mezzanine.pages.page_processors import processor_for
from refs.models import Source

@processor_for('activities/publications')
def exomol_publications(request, page):
    sources = Source.objects.filter(tags__name='exomol').order_by('-year')

    linelist_sources = sources.filter(tags__name='linelist')
    services_sources = sources.filter(tags__name='services')
    other_sources = sources.exclude(tags__name__in=('linelist', 'services'))

    c = {'linelist_sources': linelist_sources,
         'services_sources': services_sources, 'other_sources': other_sources}
    return c


