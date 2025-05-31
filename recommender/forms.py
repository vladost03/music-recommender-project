from django import forms
from .models import UserPreference

GENRE_CHOICES = [
    ('personal_mix', 'Personal Mix (Based on your listening history)'),
    ('rock', 'Rock'),
    ('pop', 'Pop'),
    ('jazz', 'Jazz'),
    ('hip-hop', 'Hip Hop'),
    ('classical', 'Classical'),
    ('electronic', 'Electronic'),
    ('reggae', 'Reggae'),
    ('metal', 'Metal'),
    ('blues', 'Blues'),
    ('country', 'Country'),
]

class UserPreferenceForm(forms.ModelForm):
    genre = forms.ChoiceField(choices=GENRE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = UserPreference
        fields = ['genre']