from django import forms

class UploadBibTexFileForm(forms.Form):
    file = forms.FileField(label='Select a BibTeX file',
                           help_text='max. 1 MB')

