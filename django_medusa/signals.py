from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from tasks import update_paths


@receiver(post_save)
def post_save_renderer(sender, instance, **kwargs):
    if hasattr(sender, 'render_static'):
        paths = instance.render_static()
        if getattr(settings, 'MEDUSA_UPDATE_ASYNC', False):
            update_paths.delay(paths)
        else:
            update_paths(paths)
