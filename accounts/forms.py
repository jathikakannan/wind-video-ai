from django import forms
from .models import UploadedFile


class UploadForm(forms.ModelForm):

    class Meta:
        model = UploadedFile
        fields = ['file', 'file_type']


from .models import Video

class VideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['video']
