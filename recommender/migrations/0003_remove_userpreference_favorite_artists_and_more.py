# Generated by Django 5.2.1 on 2025-05-30 10:20

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recommender', '0002_userpreference'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userpreference',
            name='favorite_artists',
        ),
        migrations.RemoveField(
            model_name='userpreference',
            name='favorite_genres',
        ),
    ]
