# Generated by Django 5.2.1 on 2025-05-29 23:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommender', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_session_key', models.CharField(max_length=100)),
                ('favorite_genres', models.CharField(blank=True, max_length=255)),
                ('favorite_artists', models.CharField(blank=True, max_length=255)),
                ('genre', models.CharField(blank=True, max_length=100)),
                ('mood', models.CharField(blank=True, max_length=100)),
                ('tempo', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
