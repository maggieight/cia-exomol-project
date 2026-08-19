from django.utils.safestring import mark_safe
from django import forms

class XsecSearchForm(forms.Form):
    dnu = forms.FloatField()
    dnu.label = mark_safe('&Delta;<em>&nu;</em>')
    numin = forms.FloatField(min_value=0.)
    numin.label = mark_safe('<em>&nu;</em><sub>min</sub>')
    numax = forms.FloatField(min_value=0.)
    numax.label = mark_safe('<em>&nu;</em><sub>max</sub>')
    T = forms.FloatField()
    T.label = mark_safe('<em>T</em>')

    spoon_feed = forms.BooleanField(required=False)
    spoon_feed.label = mark_safe('Two-column output: <em>&nu;</em> and'
                                 ' <em>&sigma;</em>')

    # so we can colour erroneous fields in the registration form
    error_css_class = 'has-error'

    def __init__(self, xsec_meta, *args, **kwargs):
        self.xsec_meta = xsec_meta
        super(XsecSearchForm, self).__init__(*args, **kwargs)

        self.fields['numin'].label = mark_safe('<em>&nu;</em><sub>min</sub> ('
                '%g - %g cm<sup>-1</sup>)' % (self.xsec_meta.numin,
                                              self.xsec_meta.numax))
        self.fields['numin'].min_value = self.xsec_meta.numin
        self.fields['numin'].max_value = self.xsec_meta.numax
        self.fields['numax'].label = mark_safe('<em>&nu;</em><sub>max</sub> ('
                '%g - %g cm<sup>-1</sup>)' % (self.xsec_meta.numin,
                                              self.xsec_meta.numax))
        self.fields['numax'].min_value = self.xsec_meta.numin
        self.fields['numax'].max_value = self.xsec_meta.numax
        of = xsec_meta.isotopologue.ordinary_formula
        self.fields['T'].label = mark_safe('<em>T</em> (%d - %d K)'\
                                 % (int(xsec_meta.Tmin), int(xsec_meta.Tmax)))
        self.fields['T'].min_value = xsec_meta.Tmin
        self.fields['T'].max_value = xsec_meta.Tmax

    def clean_dnu(self):
        xdnu = self.cleaned_data['dnu']
        if xdnu < self.xsec_meta.dnu or xdnu > 100.:
            raise forms.ValidationError(mark_safe('&Delta;<em>&nu;</em> must'
                ' be between %g and 100 cm<sup>-1</sup>' % self.xsec_meta.dnu))
        return xdnu

    def clean_T(self):
        T = self.cleaned_data['T']
        if T > self.xsec_meta.Tmax:
            raise forms.ValidationError(mark_safe('Maximum T is %d K for %s'\
                % (self.xsec_meta.Tmax,
                   self.xsec_meta.isotopologue.ordinary_formula_html())))
        if T < self.xsec_meta.Tmin:
            raise forms.ValidationError(mark_safe('Minimum T is %d K for %s'\
                % (self.xsec_meta.Tmax,
                   self.xsec_meta.isotopologue.ordinary_formula_html())))
        return T

    def clean_numax(self):
        xnumax = self.cleaned_data['numax']
        try:
            xdnu = self.cleaned_data['dnu']
        except KeyError:
            return xnumax
        numax = self.xsec_meta.numax - xdnu/2. + self.xsec_meta.dnu/2.
        if xnumax > numax:
            raise forms.ValidationError(mark_safe('Maximum <em>&nu;</em> at'
                         ' this binning interval is %d cm<sup>-1</sup> for %s'
                % (numax, self.xsec_meta.isotopologue.ordinary_formula_html())))

        xnumin = self.cleaned_data['numin']
        if xnumin >= xnumax:
            raise forms.ValidationError(mark_safe('<i>ν</i><sub>min</sub> cannot be'
                        ' greater than <i>ν</i><sub>max</sub>!'))

        return min(xnumax, numax)

    def clean_numin(self):
        xnumin = self.cleaned_data['numin']
        if xnumin > self.xsec_meta.numax:
            raise forms.ValidationError(mark_safe('Minimum <em>&nu;</em>'
                         ' must not be greater than %d cm<sup>-1</sup> for %s'
                                 % (self.xsec_meta.numax,
                        self.xsec_meta.isotopologue.ordinary_formula_html())))
        return xnumin


