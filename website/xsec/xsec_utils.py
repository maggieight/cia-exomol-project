import os
import sys
from exomol3.settings import RESULTS_DIR, DATA_DIR, NODEID
from xsec.xsec_xsams import write_xsams
from xsec.models import XsecMeta
from data.models import DataCollection
import math
from glob import glob
from array import array

import logging
logger = logging.getLogger(__name__)

Tgrid = {}
def get_Tgrids():
    """Populate dictionary of temperature grids for each isotopologue."""

    xsec_metas = XsecMeta.objects.all()
    for xsec_meta in xsec_metas:
        iso_slug = xsec_meta.isotopologue.slug
        xsec_files = glob(os.path.join(DATA_DIR, 'xsecs', iso_slug,
                          '*.bsig'))
        Tgrid[iso_slug] = []
        for xsec_file in xsec_files:
            # Cross section filenames are:
            # <iso_slug>__<dataset>__<nu-range>__<T>K__<p>bar__<res>.bsig
            T = int(os.path.basename(xsec_file).split('__')[3][:-1])
            Tgrid[iso_slug].append(T)
        Tgrid[iso_slug].sort()
        
get_Tgrids()

def write_list(filename, arr, fmt=None):
    """
    Write the values of the list (or other iterable) arr to a
    file called filename.

    """

    with open(filename, 'w') as fo:
        if fmt:
            for x in arr: print(fmt % x, file=fo)
        else:
            for x in arr: print(x, file=fo)

def write_list2(filename, xmin, dx, ygrid, fmt):
    """
    Write a list of two columns, (x,y) where x is a linear sequence determined
    by xmin + i*dx for each value in the y array. 

    """

    with open(filename, 'w') as fo:
        for i,y in enumerate(ygrid):
            x = xmin + i*dx
            print(fmt % (x,y), file=fo)

def bin_xsec(y1, xmin1, xmax1, dx1, xmin2, xmax2, dx2):
    """
    Return the list y2, which is the list y1 on a grid defined by xmin1,
    xmax1, dx1, binned onto the grid defined by xmin2, xmax2, dx2; the
    values in list y2 are weighted by dx1 / dx2.

    """

    if xmin2-0.5*dx2 < xmin1-0.5*dx1 or xmax2+0.5*dx2 > xmax1+0.5*dx1:
        # XXX?
        pass
        #logger.error('grid to bin to, (%f, %f), is out of range of original'
        #             ' grid, (%f, %f).' % (xmin2, xmax2, xmin1, xmax1))
        #sys.exit(1)

    dfac = dx1 / dx2

    # the grid we're binning *from*
    n1 = int(round((xmax1 - xmin1)/dx1)) + 1
    if n1 != len(y1):
        logger.error('inconsistent y1, xmin1, xmax1, dx1 in bin method!')
        sys.exit(1)

    # the grid we're binning *to*
    n2 = int(round((xmax2 - xmin2)/dx2)) + 1
    y2 = [0.] * n2

    j = 0
    x2lo = xmin2 - 0.5*dx2
    x2hi = xmin2 + 0.5*dx2
    for i1 in range(n1):
        x1lo = xmin1 + (i1 - 0.5)*dx1
        x1hi = x1lo + dx1
        if x1hi <= x2lo:
            continue
        w = 1.
        if x1hi > x2hi:
            if j > 0:
                w = (x2hi - x1lo) / dx1
                y2[j] += dfac * w * y1[i1]
            # move to the next bin in the binned grid
            j += 1
            if j == n2:
                break
            x2lo += dx2
            x2hi += dx2
            x2lo = xmin2 + (j - 0.5)*dx2
            x2hi = x2lo + dx2
            w = 1. - w
            y2[j] += dfac * w * y1[i1]
            continue
        y2[j] += dfac * y1[i1]
    return y2

def get_sigma(xsec_meta, T, xnumin, xnumax, xdnu, rnumin, rnumax, rdnu):
    """
    Get the cross section data at temperature T from the appropriate
    binary file, for wavenumber limits determined by xnumin, xnumax, xdnu.
    rdnu is the wavenumber spacing of the source cross section file and
    rnumin, rnumax are their wavenumber limits

    """

    # first get the necessary wavenumber limits on the source grid:
    irlo = max(0, int(round((xnumin - xdnu/2. + rdnu/2. - rnumin)/rdnu)))
    rnulo = rnumin + irlo * rdnu
    irhi = int(round((xnumax + xdnu/2. - rdnu/2. - rnumin)/rdnu))
    rnuhi = rnumin + irhi * rdnu
    rn = irhi - irlo + 1
    # and their positions in the (binary) sigma file, .bsig
    irlo = 8 * irlo
    irhi = 8 * irhi

    # get the data:
    isotopologue_slug = xsec_meta.isotopologue.slug
    dataset_name = xsec_meta.data_collection.data_set.name
    # XXX some cross sections are associated with the data set name
    # xsec-<dataset> where <dataset> is the line list data set used to create
    # them. This should be sorted out some time (not now).
    dataset_name = dataset_name.replace('xsec-', '')
    xsec_file = '%s__%s__%d-%d__%dK__0bar__0.01.cross' % (isotopologue_slug,
                   dataset_name, int(rnumin), int(rnumax), T)
    xsec_path = os.path.join(DATA_DIR, 'xsecs', isotopologue_slug, xsec_file)
    bsig_path = os.path.splitext(xsec_path)[0]+'.bsig'

    f = open(bsig_path, 'rb')
    rsigma = array('d')
    f.seek(irlo)
    rsigma.fromfile(f, rn)
    return rnulo, rnuhi, rsigma

def get_rsigma(xsec_meta, xT, xnumin, xnumax, xdnu):

    # Source, high-resolution (dnu = 0.01) spectrum file details
    rnumin = xsec_meta.numin
    rnumax = xsec_meta.numax
    rdnu = xsec_meta.dnu

    # Find the lowest temperature on Tgrid greater than the requested
    # temperature, xT: this is rTb
    this_Tgrid = Tgrid[xsec_meta.isotopologue.slug]
    i = 0
    while this_Tgrid[i] < xT:
        i += 1
    rTb = this_Tgrid[i]

    # Get the absorption cross section at rTb.
    rnulo, rnuhi, rsigmab = get_sigma(xsec_meta, rTb, xnumin, xnumax, xdnu,
                                      rnumin, rnumax, rdnu)
    if xT == rTb:
        # No interpolation needed
        return rnulo, rnuhi, rsigmab
    else:
        # Interpolate between the cross section at temperatures rTa and rTb
        # which bracket the desired temperature, xT
        # Get the highest temperature on Tgrid less than xT: this is rTa ...
        rTa = this_Tgrid[i-1]
        # ... and get the high-resolution cross section at rTa
        rnulo, rnuhi, rsigmaa = get_sigma(xsec_meta, rTa, xnumin, xnumax, xdnu,
                                          rnumin, rnumax, rdnu)

        rsigma = array('d')
        # linear interpolation:
        rdT = rTb - rTa; xdT = xT - rTa; fac = xdT/rdT
        for i in range(len(rsigmab)):
            rsigma.append(rsigmaa[i] + (rsigmab[i]-rsigmaa[i]) * fac)
        # special interpolation (which is more accurate but slower):
        if False:   # XXX put this in settings.py as a variable
            for i in range(len(rsigmab)):
                sig = 0.
                try:
                    b = math.log(rsigmaa[i]/rsigmab[i])/(1./rTb - 1./rTa)
                    a = rsigmaa[i] * math.exp(b / rTa)
                    sig = a * math.exp(-b / xT) 
                except (ZeroDivisionError, ValueError, OverflowError):
                    # resort to linear interpolation, then:
                    rdT = rTb - rTa; xdT = xT - rTa; fac = xdT/rdT
                    sig = rsigmaa[i] + (rsigmab[i]-rsigmaa[i]) * fac
                finally:
                    rsigma.append(sig)
        return rnulo, rnuhi, rsigma

def get_xsec(xsec_meta, xnumin, xnumax, xT, xdnu, spoon_feed=False):
    rdnu = xsec_meta.dnu
    rnulo, rnuhi, rsigma = get_rsigma(xsec_meta, xT, xnumin, xnumax, xdnu)
            
    # output names for .sigma and .xsams files
    xsec_stem = '%s_%d-%d_%dK_%f' % (xsec_meta.isotopologue.slug,
                                     int(xnumin), int(xnumax), int(xT), xdnu)
    sigma_name = '%s.sigma' % xsec_stem
    sigma_path = os.path.join(RESULTS_DIR, sigma_name)
    xsams_name = '%s.xsams' % xsec_stem
    xsams_path = os.path.join(RESULTS_DIR, xsams_name)

    if (xdnu - rdnu) < 1.e-5 and (int(xnumin/rdnu) - xnumin/rdnu) < 1.e-5:
        # the requested grid spacing is pretty much the same as the source
        # cross sections' grid spacing, so just write it directly to a file
        if spoon_feed:
            write_list2(sigma_path, rnulo, rdnu, rsigma, '%12.6f %14.8e')
        else:
            write_list(sigma_path, rsigma, '%14.8e')
    else:
        # bin the cross section to the desired wavenumber grid spacing
        xsigma = bin_xsec(rsigma, rnulo, rnuhi, rdnu, xnumin, xnumax, xdnu)
        if spoon_feed:
            write_list2(sigma_path, xnumin, xdnu, xsigma, '%12.6f %14.8e')
        else:
            write_list(sigma_path, xsigma, '%14.8e')

    # get the sources
    data_collection=DataCollection.objects.filter(data_type__type_str='xsec')\
                    .filter(isotopologue=xsec_meta.isotopologue)\
                    .filter(data_set__name__startswith='xsec-').get()
    sources = data_collection.source.all()

    # write the XSAMS document to go with this .sigma file
    comment = '%s cross section calculated from ExoMol (www.exomol.com)'\
                     % xsec_meta.isotopologue.ordinary_formula
    write_xsams(NODEID, 1, comment, sources, xT,
                xsec_meta.isotopologue, xnumin, xnumax, xdnu, sigma_name,
                xsams_path)

    search_summary = {'summary': '',
                      'numin': xnumin, 'numax': xnumax, 'T': xT, 'dnu': xdnu,
                      'output_files': [sigma_name, xsams_name],
                      'sources': sources,
                      }
    return search_summary
