from django import template
register = template.Library()

@register.filter
def has_def_file(dataset):
    """Return True if dataset has a .def file, otherwise False."""

    if dataset.external or dataset.name.startswith('xsec'):
        return False
    return True
