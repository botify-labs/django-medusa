from celery.task.base import task
from django_medusa.renderers import StaticSiteRenderer


@task
def update_paths(paths):
    StaticSiteRenderer.initialize_output()
    k = StaticSiteRenderer()
    k._paths = paths
    k.generate()
    StaticSiteRenderer.finalize_output()
