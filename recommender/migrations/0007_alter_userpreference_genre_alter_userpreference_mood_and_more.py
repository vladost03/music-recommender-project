# Generated by Django 5.2.1 on 2025-05-31 10:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommender', '0006_alter_userpreference_genre_alter_userpreference_mood_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userpreference',
            name='genre',
            field=models.CharField(choices=[('rock', 'Rock'), ('pop', 'Pop'), ('jazz', 'Jazz'), ('hip-hop', 'Hip Hop'), ('classical', 'Classical'), ('electronic', 'Electronic'), ('reggae', 'Reggae'), ('metal', 'Metal'), ('blues', 'Blues'), ('country', 'Country')], max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='userpreference',
            name='mood',
            field=models.CharField(choices=[('happy', 'Happy'), ('sad', 'Sad'), ('energetic', 'Energetic'), ('calm', 'Calm')], max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='userpreference',
            name='tempo',
            field=models.CharField(choices=[('slow', 'Slow'), ('medium', 'Medium'), ('fast', 'Fast')], max_length=50, null=True),
        ),
    ]
