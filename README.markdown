# django-medusa

Allows rendering a Django-powered website into a static website a la *Jekyll*,
*Movable Type*, or other static page generation CMSes or frameworks.
**django-medusa** is designed to be as simple as possible and allow the
easy(ish) conversion of existing dynamic Django-powered websites -- nearly any
existing Django site installation (not relying on highly-dynamic content) can
be converted into a static generator which mirror's that site's output.

Given a "renderer" that defines a set of URLs (see below), this uses Django's
built-in `TestClient` to render out those views to either disk, Amazon S3,
or to Google App Engine.

At the moment, this likely does not scale to extremely large websites.

Optionally utilizes the `multiprocessing` library to speed up the rendering
process by rendering many views at once.

**For those uninterested in the nitty-gritty**, there are tutorials/examples
in the `docs` dir:

* [Tutorial 1: Hello World](https://github.com/mtigas/django-medusa/blob/master/docs/TUTORIAL-01.markdown)

## Botify Labs Note

We updated the initial lib from [mtigas](https://github.com/mtigas/django-medusa/blob/master/docs/TUTORIAL-01.markdown) to be compatible with multiple subdomains / AWS Cloudfront / `django-hosts` module.

We nedeed to compute different paths depending on subdomains, but as you may know, it's not possible with cloudfront to push files in the same bucket but for different domains.

So we change renderers to return a dict instead of a path, adding the host identifier and the S3 Bucket where path will be pushed

Ex : 
    {
        "path": "/blog",
        "host": "www",
        "bucket": "my_s3_bucket
    }

`host` is the django-host identifier, it's needed because django's client module needs a HTTP_HOST to map the path with the good subdomain.

## Renderer classes

Renderers live in `renderers.py` in each `INSTALLED_APP`.

Simply subclassing the `StaticSiteRenderer` class and defining `get_paths`
works:

    from django_medusa.renderers import StaticSiteRenderer

    class HomeRenderer(StaticSiteRenderer):
        def get_paths(self):
            return frozenset([
                "/",
                "/about/",
                "/sitemap.xml",
            ])

    renderers = [HomeRenderer, ]

A more complex example:

    from django_medusa.renderers import StaticSiteRenderer
    from myproject.blog.models import BlogPost


    class BlogPostsRenderer(StaticSiteRenderer):
        def get_paths(self):
            paths = ["/blog/", ]

            items = BlogPost.objects.filter(is_live=True).order_by('-pubdate')
            for item in items:
                paths.append(item.get_absolute_url())

            return paths

    renderers = [BlogPostsRenderer, ]

Or even:

    from django_medusa.renderers import StaticSiteRenderer
    from myproject.blog.models import BlogPost
    from django.core.urlresolvers import reverse


    class BlogPostsRenderer(StaticSiteRenderer):
        def get_paths(self):
            # A "set" so we can throw items in blindly and be guaranteed that
            # we don't end up with dupes.
            paths = set(["/blog/", ])

            items = BlogPost.objects.filter(is_live=True).order_by('-pubdate')
            for item in items:
                # BlogPost detail view
                paths.add(item.get_absolute_url())

                # The generic date-based list views.
                paths.add(reverse('blog:archive_day', args=(
                    item.pubdate.year, item.pubdate.month, item.pubdate.day
                )))
                paths.add(reverse('blog:archive_month', args=(
                    item.pubdate.year, item.pubdate.month
                )))
                paths.add(reverse('blog:archive_year', args=(item.pubdate.year,)))

            # Cast back to a list since that's what we're expecting.
            return list(paths)

    renderers = [BlogPostsRenderer, ]

## Renderer backends

### Disk-based static site renderer

Example settings:

    INSTALLED_APPS = (
        # ...
        # ...
        'django_medusa',
    )
    # ...
    MEDUSA_RENDERER_CLASS = "django_medusa.renderers.DiskStaticSiteRenderer"
    MEDUSA_MULTITHREAD = True
    MEDUSA_DEPLOY_DIR = os.path.abspath(os.path.join(
        REPO_DIR,
        'var',
        "html"
    ))

### S3-based site renderer

Example settings:

    INSTALLED_APPS = (
        # ...
        # ...
        'django_medusa',
    )
    # ...
    MEDUSA_RENDERER_CLASS = "django_medusa.renderers.S3StaticSiteRenderer"
    MEDUSA_MULTITHREAD = True
    AWS_ACCESS_KEY = ""
    AWS_SECRET_ACCESS_KEY = ""
    MEDUSA_AWS_STORAGE_BUCKET_NAME = "" # (also accepts AWS_STORAGE_BUCKET_NAME)

Be aware that the S3 renderer will overwrite any existing files that match
URL paths in your site.

The S3 backend will force "index.html" to be the Default Root Object for each
directory, so that "/about/" would actually be uploaded as "/about/index.html",
but properly loaded by the browser at the "/about/" URL.

**BONUS:** Additionally, the S3 renderer keeps the "Content-Type" HTTP header
that the view returns: if "/foo/json/" returns a JSON file (application/json),
the file will be uploaded to "/foo/json/index.html" but will be served as
application/json in the browser -- and will be accessible from "/foo/json/".

### App Engine-based site renderer

Example settings:

    INSTALLED_APPS = (
        # ...
        # ...
        'django_medusa',
    )
    # ...
    MEDUSA_RENDERER_CLASS = "django_medusa.renderers.GAEStaticSiteRenderer"
    MEDUSA_MULTITHREAD = True
    MEDUSA_DEPLOY_DIR = os.path.abspath(os.path.join(
        REPO_DIR,
        'var',
        "html"
    ))
    GAE_APP_ID = ""

This generates a `app.yaml` file and a `deploy` directory in your
`MEDUSA_DEPLOY_DIR`. The `app.yaml` file contains the URL mappings to upload
the entire site as a static files.

App Engine generally follows filename extensions as the mimetype. If you have
paths that don't have an extension and are *not* HTML files (i.e.
"/foo/json/", "/feeds/blog/", etc.), the mimetype from the "Content-Type" HTTP
header will be manually defined for this URL in the `app.yaml` path.

## Collecting static media
Django Medusa will collect static files for you after the static site code is generated if you add:

    MEDUSA_COLLECT_STATIC = True

to your `settings.py`. Optionally, you may specify a list of patterns to exclude by adding:

    MEDUSA_COLLECT_STATIC_IGNORE = ['admin', 'less']

### Specifying the static media collection directory
By default, static files will be collected to the directory specified by `STATIC_ROOT`. If you wish to provide a different directory, you may do so via a django-medusa specific settings file, in which you can override `STATIC_ROOT`:

Given the directory structure of:

    your_app/
        build/ <- MEDUSA_DEPLOY_DIRECTORY

        your_app/
            settings.py
            medusa_settings.py

and the following values in `medusa_settings.py`:

    import os
    from .settings import *

    STATIC_ROOT = os.path.join(MEDUSA_DEPLOY_DIRECTORY, 'static')

you can now run:

    $ python manage.py staticsitegen --settings=your_app.medusa_settings

and static media will be collected to your django-medusa specific directory.

## Partial rendering

Just implement a `render_static` method in your model.

In this example, when you update a post, it will recompute the permalink page, but also blog's homepage. (Considering that you won't necessary need to compute other posts)

    class BlogPostsRenderer(StaticSiteRenderer):
        def render_static(self):
            return ["/blog/", iterm.get_absolute_url()]

Rendering of will be called in a `post_save`.

If you want it to be computed asynchronously, we add in your settings.py : 

    MEDUSA_UPDATE_ASYNC = True


## Usage

1. Install `django-medusa` into your python path via pip: `$ pip install django-medusa` or download and run `python setup.py` and add
   `django_medusa` to `INSTALLED_APPS`.
2. Select a renderer backend (currently: disk or s3) and other options in your settings.
2. Create renderer classes in `renderers.py` under the apps you want to render.
3. `django-admin.py staticsitegen` (optionally provide a specific settings file)
4. Deploy the static version of your site.
5. Profit!

### Example

From the first example in the "**Renderer classes**" section, using the
disk-based backend.

    $ django-admin.py staticsitegen
    Found renderers for 'myproject'...
    Skipping app 'django.contrib.syndication'... (No 'renderers.py')
    Skipping app 'django.contrib.sitemaps'... (No 'renderers.py')
    Skipping app 'typogrify'... (No 'renderers.py')

    Generating with up to 8 processes...
    /project_dir/var/html/index.html
    /project_dir/var/html/about/index.html
    /project_dir/var/html/sitemap.xml
