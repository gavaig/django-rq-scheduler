import sys
from datetime import datetime

import click
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from scheduler.models import JobArg, JobKwarg
from scheduler.tools import MODEL_NAMES


def create_job_from_dict(job_dict, update):
    model = apps.get_model(app_label='scheduler', model_name=job_dict['model'])
    existing_job = model.objects.filter(name=job_dict['name']).first()
    if existing_job:
        if update:
            click.echo(f'Found existing job "{existing_job}, removing it to be reinserted"')
            existing_job.delete()
        else:
            click.echo(f'Found existing job "{existing_job}", skipping')
            return
    kwargs = dict(job_dict)
    del kwargs['model']
    del kwargs['callable_args']
    del kwargs['callable_kwargs']
    if 'scheduled_time' in kwargs:
        kwargs['scheduled_time'] = datetime.fromisoformat(kwargs['scheduled_time'])

    scheduled_job = model.objects.create(**kwargs)
    click.echo(f'Created job {scheduled_job}')
    content_type = ContentType.objects.get_for_model(scheduled_job)

    for arg in job_dict['callable_args']:
        JobArg.objects.create(
            content_type=content_type, object_id=scheduled_job.id, **arg, )
    for arg in job_dict['callable_kwargs']:
        JobKwarg.objects.create(
            content_type=content_type, object_id=scheduled_job.id, **arg, )


class Command(BaseCommand):
    """
    Import scheduled jobs
    """
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            '-f', '--format',
            action='store',
            choices=['json', 'yaml'],
            default='json',
            dest='format',
            help='format of input',
        )
        parser.add_argument(
            '--filename',
            action='store',
            dest='filename',
            help='File name to load (otherwise loads from standard input)',
        )

        parser.add_argument(
            '-r', '--reset',
            action='store_true',
            dest='reset',
            help='Remove all currently scheduled jobs before importing',
        )
        parser.add_argument(
            '-u', '--update',
            action='store_true',
            dest='update',
            help='Update existing records',
        )

    def handle(self, *args, **options):
        file = open(options.get('filename')) if options.get("filename") else sys.stdin
        jobs = list()
        if options.get("format") == 'json':
            import json
            try:
                jobs = json.load(file)
            except json.decoder.JSONDecodeError:
                click.echo('Error decoding json', err=True)

        if options.get("format") == 'yaml':
            try:
                import yaml
            except ImportError:
                click.echo("Aborting. LibYAML is not installed.")
                return
            # Disable YAML alias
            yaml.Dumper.ignore_aliases = lambda *x: True
            jobs = yaml.load(file, yaml.SafeLoader)

        if options.get('reset'):
            for model_name in MODEL_NAMES:
                model = apps.get_model(app_label='scheduler', model_name=model_name)
                model.objects.delete()

        for job in jobs:
            create_job_from_dict(job, update=options.get('update'))
