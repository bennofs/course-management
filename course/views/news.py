from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _
from django.http import HttpRequest

from course.models import news
from course.forms import NewsForm

from util.error.reporting import db_error


@login_required()
@permission_required('news.add_news')
def create(request):
    if request.method == 'POST':
        form = NewsForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('overview-news')

    else:
        form = NewsForm()
        form.initial['entry'] = _((
            'English is a weakly typed, interpreted language and runs on a '
            'large number of modern humanoids with varying support for '
            'advanced syntax features. Website: https://oed.com'
        ))

    return render(
        request,
        'news/create.html',
        {
            'title': _('New News'),
            'form': form
        }
    )


@login_required()
@permission_required('news.change_news')
def edit(request: HttpRequest, news_id: str):
    """
    Edit form for changing a news and handler for submitted data.

    :param request: request object
    :param news_id: id for the news
    :return:
    """
    try:
        cur_news = news.News.objects.get(id=news_id)
    except news.News.DoesNotExist:
        return db_error(_('Requested News does not exist.'))

    if request.method == 'POST':
        form = NewsForm(request.POST, instance=cur_news)

        if form.is_valid():
            cur_news.save()
            return redirect('overview-news')

    else:
        form = NewsForm(instance=cur_news)
    return render(
        request,
        'news/edit.html',
        {
            'title': _('Edit News'),
            'form': form,
            'news_id': news_id
        }
    )


@login_required
@permission_required('news.delete_news')
def delete(request: HttpRequest, news_id: str):
    """
    Delete a news entry.

    :param request: request object
    :param news_id: id for the news
    :return:
    """
    try:
        cur_news = news.News.objects.get(id=news_id)
    except news.News.DoesNotExist:
        return db_error(_('Requested News does not exist.'))

    cur_news.delete()
    return redirect('overview-news')


def overview(request):
    return render(
        request,
        'news/overview.html',
        {
            'title': _('News Overview'),
            'news': news.News.objects.order_by('-id')
        }
    )
