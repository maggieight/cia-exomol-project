from django.shortcuts import render, get_object_or_404
from django.template import RequestContext
from chem.models import Isotopologue
from xsec.models import XsecMeta
from xsec.forms import XsecSearchForm
from xsec.xsec_utils import get_xsec

def isotopologue_xsec(request, isotopologue_slug):
    isotopologue = get_object_or_404(Isotopologue, slug=isotopologue_slug)

    c = {}
    c['isotopologue'] = isotopologue
    xsec_meta = get_object_or_404(XsecMeta, isotopologue=isotopologue)
    c['xsec_meta'] = xsec_meta

    form = XsecSearchForm(xsec_meta, request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            # do the search and redirect to results
            c.update(do_search(form))
            return render(request, 'pages/xsec/xsec_results.html', c)
    else:
        # an unbound form
        form = XsecSearchForm(xsec_meta)
    c['form'] = form
    return render(request, 'pages/xsec/isotopologue_xsec.html', c)

def do_search(form):
    xsec_meta = form.xsec_meta
    # requested wavenumber limits, temperature and grid-spacing:
    xnumin = form.cleaned_data['numin']
    xnumax = form.cleaned_data['numax']
    xT = form.cleaned_data['T']
    xdnu = form.cleaned_data['dnu']
    # spoon_feed is True for two-column (nu, sigma) output; default is
    # to output sigma only (spoon_feed=False)
    spoon_feed = form.cleaned_data['spoon_feed']

    return get_xsec(xsec_meta, xnumin, xnumax, xT, xdnu, spoon_feed)
