from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.core.context_processors import csrf
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from exomol.meta import molecules, molecule_list_html, keywords
from chem.models import Molecule
from refs.models import Source
from refs.models import refs_search, add_ref_from_bibxml
from refs.forms import UploadBibTexFileForm
from xml.dom import minidom

def bibliography(request):
    """
    Returns a menu page for searching for bibliographic data on a species.

    """

    c = {}
    c.update(csrf(request))
    if request.method == 'GET' and 'molecule_search_submit' in request.GET\
                               and 'molecule_search' in request.GET:
        ordinary_formula = request.GET['molecule_search']
        try:
            molecule = Molecule.objects.get(ordinary_formula=ordinary_formula)
            keyword = request.GET['search']
            return molecule_bibliography(request, molecule, keyword)
        except Molecule.DoesNotExist:
            c['error'] = 'Molecule %s not found.' % ordinary_formula

    if 'search' in request.GET and 'search_submit' in request.GET:
        search_terms = request.GET['search'].strip()
        if search_terms:
            sources = refs_search(search_terms )
            if not sources:
                c['error'] = 'No references found matching search terms: %s'\
                              % search_terms
            else:
                c['search_terms'] = search_terms 
                c['sources'] = sources
                return render(request, 'source_search_results.html', c)

    c['molecule_list_html'] = molecule_list_html
    return render(request, 'bibliography.html', c)

def molecule_bibliography(request, molecule, keyword):
    """
    Returns the bibliography for a Molecule object, molecule.

    """

    c = {}
    c['molecule'] = molecule
    sources = Source.objects.filter(tags__name=molecule.ordinary_formula)
    if keyword:
        sources = sources.filter(tags__name=keyword)
        c['filtered_by'] = keyword
    else:
        c['keywords'] = keywords[molecule.ordinary_formula]
    if sources.count() == 0:
        c['error'] = 'No references found for this molecule.'
    else:
        c['sources'] = sources
    return render(request, 'molecule_bibliography.html', c)

def molecule_bibliography_from_slug(request, molecule_slug):
    """
    Returns the bibliography for the molecule identified by molecule_slug.

    """

    try:
        molecule = molecules[molecule_slug]
    except KeyError:
        raise Http404

    keyword = request.GET.get('keyword')

    return molecule_bibliography(request, molecule, keyword)

def source_list_save(request):
    c = {}

    output_format = request.POST.get('output_format')
    if not output_format:
        raise Http404

    kwargs = {}
    if output_format == 'Text':
        output_method = '__str__'
        content_type='text/plain'
    elif output_format == 'XSAMS':
        output_method = 'xsams'
        kwargs['NODEID'] = 'EXOMOL'
        content_type='text/xml'
    elif output_format == 'BibTeX':
        output_method = 'bibtex'
        kwargs['prefix'] = 'EXOMOL'
        content_type='text/plain'
    else:
        raise Http404

    source_ids = [int(s_id) for s_id in request.POST.getlist('source_id')]
    sources = Source.objects.filter(pk__in=source_ids)
    
    sources_output = []
    for source in sources:
        sources_output.append(getattr(source, output_method)(**kwargs))
    return HttpResponse('\n'.join(sources_output), content_type=content_type)

@login_required
def upload_ref(request):

    # TODO check user has permissions to upload references

    c = {}
    c.update(csrf(request))
    if request.method == 'POST':
        form = UploadBibTexFileForm(request.POST, request.FILES)
        if form.is_valid():
            # process form
            bibfile = request.FILES['file']
            c['biblines'] = process_bib_upload(bibfile)
            c['filename'] = bibfile.name
            return render(request, 'bib_upload_summary.html', c)
    else:
        form = UploadBibTexFileForm()
        c['form'] = form

    return render(request, 'bibliography_upload.html', c)

def process_bib_upload(bibfile):
    biblines = bibfile

    html = []
    xmldoc = minidom.parse(bibfile)
    entry_list = xmldoc.getElementsByTagName('bibxml:entry')
    for entry_bibxml in entry_list:
        msg, warnings = add_ref_from_bibxml(entry_bibxml)
        html.append('<p>%s - <span style="color:red">%s</span></p>'
                        % (msg, ', '.join(warnings)))

    return '\n'.join(html)
