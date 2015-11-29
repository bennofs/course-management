from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from django.shortcuts import redirect, render_to_response, render
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _

from course.forms import CourseForm, AddTeacherForm, NotifyCourseForm
from course.models.course import Course
from course.models.schedule import Schedule
from course.models.subject import Subject
from course.util.permissions import needs_teacher_permissions

from user.models import UserInformation

from util import html_clean
from util.error.reporting import db_error
from util.routing import redirect_unless_target


DEFAULT_COURSE_DESCRIPTION = """\
# The Hitchhikers Guide To The Galaxy

We will explore the universe.

## Materials

- a towel
- lots of courage
"""


def course(request, course_id):
    try:
        current_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))

    try:
        user = request.user.userinformation
        if isinstance(user, UserInformation):
            context = current_course.as_context(user)
        else:
            context = current_course.as_context()

        return render(
            request,
            'course/info.html',
            context
        )
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))


@needs_teacher_permissions
def edit_course(request, course_id):
    try:
        current_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))

    if request.method == "POST":

        form = CourseForm(request.POST, instance=current_course)

        if form.is_valid():
            current_course.save()
            return redirect('course', course_id)

    else:
        form = CourseForm(instance=current_course)
    return render(
        request,
        'course/edit.html',
        {
            'title': _('Edit course'),
            'form': form,
            'course_id': course_id,
            'allowed_tags': html_clean.DESCR_ALLOWED_TAGS,
            'course_is_active': current_course.active,
        }
    )


@needs_teacher_permissions
@require_POST
def toggle(request, course_id, active):
    try:
        curr_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))

    curr_course.active = active
    if not active:
        curr_course.participants.clear()
        curr_course.queue.clear()
    curr_course.save()
    return redirect('course', course_id)


@permission_required('course.add_course')
def create(request):

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            created = form.save(commit=False)

            created.schedule = Schedule.objects.create(_type=form['schedule_type'])
            created.save()
            created.teacher.add(request.user.UserInformation)

            return redirect('course', created.id)
    else:
        form = CourseForm(initial={
            'description': DEFAULT_COURSE_DESCRIPTION,
            'max_participants': 30,
            'archiving': 't'
        })
        if 'subject' in request.GET:
            subj = int(request.GET['subject'][0])
            if Subject.objects.filter(id=subj).exists():
                form.initial['subject'] = subj

    return render(
        request,
        'course/create.html',
        {
            'title': _('New Course'),
            'form': form
        }
    )


@login_required()
@require_POST
@permission_required('course.delete_course')
def delete(request, course_id):
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))

    subj = course.subject.name

    course.delete()
    return redirect('subject', subj)


@needs_teacher_permissions
def add_teacher(request, course_id):
    context = {
        'title': _('Edit Teachers'),
        'course_id': course_id,
        'target': reverse('add-teacher', args=(course_id,))
    }

    try:
        curr_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))

    if request.method == 'POST':
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(username=form.cleaned_data['username'])

                curr_course.teacher.add(user.UserInformation)

                return redirect('add-teacher', course_id)
            except User.DoesNotExist:
                context['error'] = _('The username you entered does not exist in '
                                     'my database, sorry :(')
    else:
        form = AddTeacherForm()

    context['form'] = form
    context['teachers'] = curr_course.teacher

    return render(
        request,
        'course/teacher.html',
        context
    )


@needs_teacher_permissions
@require_POST
def remove_teacher(request, course_id, teacher_id):
    try:
        Course.objects.get(id=course_id).teacher.remove(UserInformation.objects.get(id=teacher_id))
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))
    except UserInformation.DoesNotExist:
        return db_error(_('Requested student does not exist.'))
    return redirect_unless_target(request, 'course', course_id)


@needs_teacher_permissions
def notify(request: HttpRequest, course_id):
    if request.method == 'POST':
        form = NotifyCourseForm(request.POST)
        if form.is_valid():

            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return db_error(_('Requested course does not exist.'))

            email = request.user.email

            data = form.cleaned_data

            show_sender = data.get('show_sender', False) and email

            subject = form.subject
            content = form.content

            for student in course.participants.all():
                if show_sender:
                    student.user.email_user(subject, content, email)
                else:
                    student.user.email_user(subject, content)

            return redirect('notify-course-done', course_id)

    else:
        form = NotifyCourseForm()

    return render(
        request,
        'course/notify.html',
        {
            'title': _('Notify Course'),
            'form': form,
            'course_id': course_id
        }
    )


@needs_teacher_permissions
def notify_done(request, course_id):
    return render_to_response('course/notify-done.html')


@needs_teacher_permissions
def remove_student(request: HttpRequest, course_id:str, UserInformation_id:str):
    try:
        course = Course.objects.get(id=course_id)
        course.unenroll(UserInformation_id)
    except Course.DoesNotExist:
        return db_error(_('Requested course does not exist.'))
    except Course.IsEnrolled:
        return db_error(_('Requested student is not enrolled in this course.'))

    return redirect('course', course_id)
