# Generated by Django 4.1.1 on 2022-09-06 20:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assis_tech', '0004_alter_account_cpf'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='username',
            field=models.CharField(max_length=30),
        ),
    ]
