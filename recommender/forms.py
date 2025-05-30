from django import forms
from .models import UserPreference

class UserPreferenceForm(forms.ModelForm):
    class Meta:
        model = UserPreference
        fields = ['genre', 'mood', 'tempo']
        widgets = {
            'genre': forms.Select(attrs={'class': 'form-control'}),
            'mood': forms.Select(attrs={'class': 'form-control'}),
            'tempo': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'genre': 'Жанр',
            'mood': 'Настрій',
            'tempo': 'Темп',
        }
