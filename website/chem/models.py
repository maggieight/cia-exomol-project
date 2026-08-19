from django.db import models
import os
import struct
from exomol3.settings import DATA_DIR
from pyqn.quantity import Quantity
from pyvalem.formula import Formula, FormulaParseError
from refs.models import Source
from taggit.managers import TaggableManager

class UnknownRequestable(Exception):
    def __init__(self, requestable):
        msg = 'Unknown requestable for this species: "%s"' % requestable
        Exception.__init__(self, msg)

class InvalidRequestableContext(Exception):
    def __init__(self, requestable, context):
        msg = 'The context %s is not valid for the requestable "%s" of this'\
              ' species' % (str(context), requestable)
        Exception.__init__(self, msg)

class MissingRequestableContext(Exception):
    def __init__(self, requestable, context, required_context_keys):
        msg = 'The following context variables are required: %s but not'\
              ' provided in the context %s for the requestable "%s"'\
              % (str(required_context_keys), str(context), requestable) 
        Exception.__init__(self, msg)

class Index(models.Model):
    k = models.CharField(max_length=100, db_column='k')
    fk = models.CharField(max_length=100, db_column='fk')
    species_type = models.CharField(max_length=2)

    class Meta:
        db_table = 'chem_index'
        app_label = 'chem'

class Atom(models.Model):
    atomic_number = models.IntegerField(primary_key=True)
    symbol = models.CharField(max_length=3)
    name = models.CharField(max_length=20)
    atomic_weight = models.FloatField()
    atomic_weight_sd = models.FloatField(blank=True, null=True)
    configuration = models.CharField(max_length=32)
    inchi = models.CharField(max_length=11)
    inchikey = models.CharField(max_length=27)
    def __str__(self):
        return self.symbol

    class Meta:
        db_table = 'chem_atom'
        app_label = 'chem'

    def html(self):
        atomic_weight = Quantity(value=self.atomic_weight,
                                 sd=self.atomic_weight_sd, units='u')
        return '<br/>'.join([
            'Name: %s' % self.name,
            'Symbol: %s' % self.symbol,
            'Atomic Number: %d' % self.atomic_number,
            'Atomic Weight: %s' % atomic_weight.as_str(),
            'Configuration: %s' % self.configuration,
            'InChI: %s' % self.inchi,
            'InChIKey: %s' % self.inchikey,
            ])

    def get_mass(self, context):
        # the 'mass' requestable takes exactly one context variable: 'units'
        try:
            units = context['units']
        except KeyError:
            raise MissingRequestableContext('mass', context, ['units',])
        if len(context) != 1:
            raise InvalidRequestableContext('mass', context)

        mass = Quantity(value=self.atomic_weight, units='u')
        units = context.get('units')
        if units:
            mass.convert_units_to(units)
        return mass.value

    def get_simple_requestable(self, requestable, context):
        simple_requestables = {
            'atomic_number': self.atomic_number,
            'inchi': self.inchi,
            'inchikey': self.inchikey,
            'stoichiometric_formula': self.symbol,
            'ordinary_formula': self.symbol,
            'configuration': self.configuration,
        }
        # NB the caller is responsible for catching any KeyError here:
        simple_requestable = simple_requestables[requestable]
        if context:
            # there must be no context variables for a simple requestable
            raise InvalidRequestableContext(requestable, context)

        return simple_requestable

    def get_context_requestable(self, requestable, context):
        context_requestables = {
            'mass': self.get_mass,
        }
        return context_requestables[requestable](context)

    def get_requestable(self, requestable, context={}):
        try:
            return self.get_simple_requestable(requestable, context)
        except KeyError:
            try:
                return self.get_context_requestable(requestable, context)
            except KeyError:
                raise UnknownRequestable(requestable)

class Ion(models.Model):
    atom = models.ForeignKey(Atom, on_delete=models.CASCADE)
    charge = models.SmallIntegerField()
    inchi = models.CharField(max_length=20)
    inchikey = models.CharField(max_length=27)
    def __str__(self):
        return '%s%s' % (self.atom.symbol, self.s_charge())

    def s_charge(self):
        s = '{:+d}'.format(self.charge)
        if abs(self.charge) == 1:
            s = s[:-1]
        return s

    class Meta:
        db_table = 'chem_ion'
        app_label = 'chem'

    def html(self):
        formula_html = Formula(
                '%s%s' % (self.atom.symbol, self.s_charge())).html
        return '<br/>'.join([
            'Symbol: %s' % formula_html,
            'Atomic Number: %d' % self.atom.atomic_number,
            'Charge: %+d' % self.charge,
            'InChI: %s' % self.inchi,
            'InChIKey: %s' % self.inchikey,
            ])

    def get_mass(self, context):
        # the 'mass' requestable takes exactly one context variable: 'units'
        try:
            units = context['units']
        except KeyError:
            raise MissingRequestableContext('mass', context, ['units',])
        if len(context) != 1:
            raise InvalidRequestableContext('mass', context)

        # adjust for the mass of the missing or extra electrons
        # XXX is this right?
        mass = self.atom.atomic_weight - self.charge * 0.00054857990965
        mass = Quantity(value=mass, units='u')
        units = context.get('units')
        if units:
            mass.convert_units_to(units)
        return mass.value

    def get_simple_requestable(self, requestable, context):
        simple_requestables = {
            'atomic_number': self.atom.atomic_number,
            'inchi': self.inchi,
            'inchikey': self.inchikey,
            'stoichiometric_formula': '%s%s' % (self.atom.symbol,
                                                self.s_charge()),
            'ordinary_formula': '%s%s' % (self.atom.symbol, self.s_charge()),
            'charge': self.charge,
        }
        # NB the caller is responsible for catching any KeyError here:
        simple_requestable = simple_requestables[requestable]
        if context:
            # there must be no context variables for a simple requestable
            raise InvalidRequestableContext(requestable, context)

        return simple_requestable

    def get_context_requestable(self, requestable, context):
        context_requestables = {
            'mass': self.get_mass,
        }
        return context_requestables[requestable](context)

    def get_requestable(self, requestable, context={}):
        try:
            return self.get_simple_requestable(requestable, context)
        except KeyError:
            try:
                return self.get_context_requestable(requestable, context)
            except KeyError:
                raise UnknownRequestable(requestable)

class Isotope(models.Model):
    atom = models.ForeignKey(Atom, on_delete=models.CASCADE)
    mass_number = models.IntegerField()
    symbol = models.CharField(max_length=5)
    ram = models.FloatField()
    ram_sd = models.FloatField(blank=True, null=True)
    abundance = models.FloatField()
    abundance_sd = models.FloatField(blank=True, null=True)
    inchi = models.CharField(max_length=11)
    inchikey = models.CharField(max_length=27)
    nucspin = models.FloatField()
    def __str__(self):
        return '%d%s' % (self.mass_number, self.symbol)

    class Meta:
        db_table = 'chem_isotope'
        app_label = 'chem'

    def html(self):
        ram = Quantity(value=self.ram, sd=self.ram_sd)
        abundance = Quantity(value=self.abundance, sd=self.abundance_sd)
        return '<br/>'.join([
            'Name: %s-%d' % (self.atom.name, self.mass_number),
            'Symbol: <sup>%d</sup>%s' % (self.mass_number, self.symbol),
            'Atomic Number: %d' % self.atom.atomic_number,
            'Mass Number: %d' % self.mass_number,
            'Relative Atomic Mass: %s' % ram.as_str(),
            'Abundance: %s' % abundance.as_str(),
            'Nuclear Spin, <em>I</em>: %3.1f' % self.nucspin,
            'InChI: %s' % self.inchi,
            'InChIKey: %s' % self.inchikey,
            ])

    def get_mass(self, context):
        # the 'mass' requestable takes exactly one context variable: 'units'
        try:
            units = context['units']
        except KeyError:
            raise MissingRequestableContext('mass', context, ['units',])
        if len(context) != 1:
            raise InvalidRequestableContext('mass', context)

        mass = Quantity(value=self.ram, units='u')
        units = context.get('units')
        if units:
            mass.convert_units_to(units)
        return mass.value

    def get_simple_requestable(self, requestable, context):
        simple_requestables = {
            'inchi': self.inchi,
            'inchikey': self.inchikey,
            'stoichiometric_formula': '%d%s' % (self.mass_number, self.symbol),
            'ordinary_formula': '%d%s' % (self.mass_number, self.symbol),
            'configuration': self.atom.configuration,
            'nucspin': str(self.nucspin)
        }
        # NB the caller is responsible for catching any KeyError here:
        simple_requestable = simple_requestables[requestable]
        if context:
            # there must be no context variables for a simple requestable
            raise InvalidRequestableContext(requestable, context)

        return simple_requestable

    def get_context_requestable(self, requestable, context):
        context_requestables = {
            'mass': self.get_mass,
        }
        return context_requestables[requestable](context)

    def get_requestable(self, requestable, context={}):
        try:
            return self.get_simple_requestable(requestable, context)
        except KeyError:
            try:
                return self.get_context_requestable(requestable, context)
            except KeyError:
                raise UnknownRequestable(requestable)

class IsotopeIon(models.Model):
    isotope = models.ForeignKey(Isotope, on_delete=models.CASCADE)
    charge = models.SmallIntegerField()
    inchi = models.CharField(max_length=20)
    inchikey = models.CharField(max_length=27)
    def __str__(self):
        return '%d%s%s' % (self.isotope.mass_number,
                             self.isotope.symbol, self.s_charge())

    def s_charge(self):
        s = '{:+d}'.format(self.charge)
        if abs(self.charge) == 1:
            s = s[:-1]
        return s

    class Meta:
        db_table = 'chem_isotope_ion'
        app_label = 'chem'

    def html(self):
        formula_html = Formula(
                '(%d%s)%s' % (self.isotope.mass_number,
                             self.isotope.symbol, self.s_charge())).html
        return '<br/>'.join([
            'Symbol: %s' % formula_html,
            'Atomic Number: %d' % self.isotope.atom.atomic_number,
            'Mass Number: %d' % self.isotope.mass_number,
            'Charge: %+d' % self.charge,
            'InChI: %s' % self.inchi,
            'InChIKey: %s' % self.inchikey,
            ])

    def get_mass(self, context):
        # the 'mass' requestable takes exactly one context variable: 'units'
        try:
            units = context['units']
        except KeyError:
            raise MissingRequestableContext('mass', context, ['units',])
        if len(context) != 1:
            raise InvalidRequestableContext('mass', context)

        # adjust for the mass of the missing or extra electrons
        # XXX is this right?
        mass = self.isotope.ram - self.charge * 0.00054857990965
        mass = Quantity(value=mass, units='u')
        units = context.get('units')
        if units:
            mass.convert_units_to(units)
        return mass.value

    def get_simple_requestable(self, requestable, context):
        simple_requestables = {
            'inchi': self.inchi,
            'inchikey': self.inchikey,
            'stoichiometric_formula': '%d%s%s'\
                    % (self.mass_number, self.symbol, self.s_charge()),
            'ordinary_formula': '%d%s%s'\
                    % (self.mass_number, self.symbol, self.s_charge()),
            'nucspin': str(self.isotope.nucspin),
            'charge': str(self.charge),
        }
        # NB the caller is responsible for catching any KeyError here:
        simple_requestable = simple_requestables[requestable]
        if context:
            # there must be no context variables for a simple requestable
            raise InvalidRequestableContext(requestable, context)

        return simple_requestable

    def get_context_requestable(self, requestable, context):
        context_requestables = {
            'mass': self.get_mass,
        }
        return context_requestables[requestable](context)

    def get_requestable(self, requestable, context={}):
        try:
            return self.get_simple_requestable(requestable, context)
        except KeyError:
            try:
                return self.get_context_requestable(requestable, context)
            except KeyError:
                raise UnknownRequestable(requestable)

class Molecule(models.Model):
    stoichiometric_formula = models.CharField(max_length=40)
    ordinary_formula = models.CharField(max_length=80, unique=True)
    charge = models.SmallIntegerField()
    inchi = models.CharField(max_length=200, blank=True)
    inchikey = models.CharField(max_length=27, blank=True)
    cml = models.TextField(null=True, blank=True)
    slug = models.CharField(max_length=80, unique=True)
    names = models.CharField(max_length=2000, blank=True)

    tags = TaggableManager()

    def __str__(self):
        return self.ordinary_formula

    class Meta:
        db_table = 'chem_molecule'
        app_label = 'chem'

    def ordinary_formula_html(self):
        try:
            ordinary_formula_html = Formula(self.ordinary_formula).html
        except FormulaParseError:
            # TODO cope with prefixes such as "cis-", "c-", etc.
            ordinary_formula_html = self.ordinary_formula
        return ordinary_formula_html

    def is_atom(self):
        """Is this molecule, in fact, a single atom?"""
        patt = '[A-Z][a-z]?$'
        return re.match(patt, self.ordinary_formula)

    def get_inchi(self):
        return self.inchi or '[No InChI set]'

    def get_inchikey(self):
        return self.inchikey or '[No InChIKey set]'

    def html(self):
        stoichiometric_formula = Formula(self.stoichiometric_formula)
        return '<br/>'.join([
            'Ordinary Formula: %s' % ordinary_formula_html(),
            'Stoichiometric Formula: %s' % stoichiometric_formula.html,
            'Relative Molecular Mass: %f' % stoichiometric_formula.rmm,
            'InChI: %s' % self.get_inchi(),
            'InChIKey: %s' % self.get_inchikey(),
            ])
        
    def get_mass(self, context):
        # the 'mass' requestable takes exactly one context variable: 'units'
        try:
            units = context['units']
        except KeyError:
            raise MissingRequestableContext('mass', context, ['units',])
        if len(context) != 1:
            raise InvalidRequestableContext('mass', context)

        stoichiometric_formula = Formula(self.stoichiometric_formula)
        rmm = stoichiometric_formula.rmm
        mass = Quantity(value=rmm, units='u')
        units = context.get('units')
        if units:
            mass.convert_units_to(units)
        return mass.value

    def get_simple_requestable(self, requestable, context):
        simple_requestables = {
            'inchi': self.get_inchi(),
            'inchikey': self.get_inchikey(),
            'stoichiometric_formula': Formula(self.stoichiometric_formula),
            'ordinary_formula': self.ordinary_formula,
        }
        # NB the caller is responsible for catching any KeyError here:
        simple_requestable = simple_requestables[requestable]
        if context:
            # there must be no context variables for a simple requestable
            raise InvalidRequestableContext(requestable, context)

        return simple_requestable

    def get_context_requestable(self, requestable, context):
        context_requestables = {
            'mass': self.get_mass,
        }
        return context_requestables[requestable](context)

    def get_requestable(self, requestable, context={}):
        try:
            return self.get_simple_requestable(requestable, context)
        except KeyError:
            try:
                return self.get_context_requestable(requestable, context)
            except KeyError:
                raise UnknownRequestable(requestable)

class Isotopologue(models.Model):
    stoichiometric_formula = models.CharField(max_length=80)
    ordinary_formula = models.CharField(max_length=160, unique=True)
    charge = models.SmallIntegerField()
    molecule = models.ForeignKey('Molecule', on_delete=models.CASCADE)
    inchi = models.CharField(max_length=200, blank=True)
    inchikey = models.CharField(max_length=27, blank=True)
    abundance = models.FloatField(null=True, blank=True)
    cml = models.TextField(null=True, blank=True)
    slug = models.CharField(max_length=160, unique=True)

    def __str__(self):
        return self.ordinary_formula

    class Meta:
        db_table = 'chem_isotopologue'
        app_label = 'chem'

    def ordinary_formula_html(self):
        try:
            ordinary_formula_html = Formula(self.ordinary_formula).html
        except FormulaParseError:
            # TODO cope with prefixes such as "cis-", "c-", etc.
            ordinary_formula_html = self.ordinary_formula
        return ordinary_formula_html

    def get_inchi(self):
        return self.inchi or '[No InChI set]'

    def get_inchikey(self):
        return self.inchikey or '[No InChIKey set]'

    def html(self):
        try:
            ordinary_formula = Formula(self.ordinary_formula)
            ordinary_formula_html = self.ordinary_formula_html()
            mass = ordinary_formula.rmm
        except FormulaParseError:
            # TODO cope with prefixes such as "cis-", "c-", etc.
            ordinary_formula_html = self.ordinary_formula
            mass = None
        stoichiometric_formula = Formula(self.stoichiometric_formula)
        abundance = Quantity(value=self.abundance, sd=None)
        mass = Quantity(value=mass, sd=None)
        data_html = []
        data_html.append('Ordinary Formula: %s' % ordinary_formula_html)
        data_html.append('Stoichiometric Formula: %s'
                                            % stoichiometric_formula.html)
        data_html.append('InChI: %s' % self.get_inchi())
        data_html.append('InChIKey: %s' % self.get_inchikey())
        if self.abundance:
            data_html.append('Abundance: %s' % abundance.as_str())
        if mass:
            data_html.append('Molecular Mass: %s' % mass.as_str())
        sources = Source.objects.filter(tags__name=self.ordinary_formula)
        if sources:
            data_html.append('Bibliography: <a href="/research/bib/?tag=%s">'
                '%d references</a>' % (self.ordinary_formula, sources.count()))

        return '<br/>'.join(data_html)

    def get_mass(self, context):
        # the 'mass' requestable takes exactly one context variable: 'units'
        try:
            units = context['units']
        except KeyError:
            raise MissingRequestableContext('mass', context, ['units',])
        if len(context) != 1:
            raise InvalidRequestableContext('mass', context)

        stoichiometric_formula = Formula(self.stoichiometric_formula)
        rmm = stoichiometric_formula.rmm
        mass = Quantity(value=rmm, units='u')
        units = context.get('units')
        if units:
            mass.convert_units_to(units)
        return mass.value

    def get_q(self, context):
        # the 'q' requestable (partition function) takes exactly one
        # context variable: 'T'
        try:
            T = context['T']
        except KeyError:
            raise MissingRequestableContext('q', context, ['T',])
        if len(context) != 1:
            raise InvalidRequestableContext('q', context)

        q = IsotopologuePartitionFunction.objects.get(isotopologue=self)
        return q.get_at_T(context['T'])

    def get_simple_requestable(self, requestable, context):
        simple_requestables = {
            'inchi': self.get_inchi(),
            'inchikey': self.get_inchikey(),
            'stoichiometric_formula': Formula(self.stoichiometric_formula),
            'ordinary_formula': self.ordinary_formula,
            'abundance': self.abundance,
        }
        # NB the caller is responsible for catching any KeyError here:
        simple_requestable = simple_requestables[requestable]
        if context:
            # there must be no context variables for a simple requestable
            raise InvalidRequestableContext(requestable, context)

        return simple_requestable

    def get_context_requestable(self, requestable, context):
        context_requestables = {
            'mass': self.get_mass,
            'q': self.get_q,
        }
        return context_requestables[requestable](context)

    def get_requestable(self, requestable, context={}):
        try:
            return self.get_simple_requestable(requestable, context)
        except KeyError:
            try:
                return self.get_context_requestable(requestable, context)
            except KeyError:
                raise UnknownRequestable(requestable)

    def xsams(self, NODEID=None):
        #for xsams_chunk in self.xsams_chunks(NODEID):
        #    yield xsams_iso_chunk
        return '\n'.join([xsams_chunk for xsams_chunk in
                                            self.xsams_chunks(NODEID)])
        
    def xsams_chunks(self, NODEID=None):
        speciesID = 'X%s-%s' % (NODEID, self.get_inchikey()) 
        yield '<Molecule speciesID="%s">' % speciesID
        yield '    <MolecularChemicalSpecies>'
        yield '    <OrdinaryStructuralFormula>'
        yield '        <Value>%s</Value>' % self.ordinary_formula
        yield '    </OrdinaryStructuralFormula>'
        yield '    <StoichiometricFormula>%s</StoichiometricFormula>'\
                        % self.stoichiometric_formula
        try:
            yield '    <ChemicalName><Value>%s</Value></ChemicalName>'\
                            % self.common_name
        except AttributeError:
            pass
        if self.inchi:
            yield '    <InChI>%s</InChI>' % self.inchi
        if self.inchikey:
            yield '    <InChIKey>%s</InChIKey>' % self.inchikey
        yield '    </MolecularChemicalSpecies>'
        yield '</Molecule>'

SpeciesModel = {
    'a': Atom,
    'ia': Isotope,
    'j': Ion,
    'ij': IsotopeIon,
    'm': Molecule,
    'im': Isotopologue,
}
