from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from course_management.forms import EditCourseForm, CreateCourseForm, AddTeacherForm
from course_management.models.course import Course
from course_management.models.schedule import Schedule
from course_management.models.subject import Subject
from course_management.util.permissions import needs_teacher_permissions
from course_management.views.base import render_with_default
from user_management.models import Student
from util import html_clean
from util.error.reporting import db_error
from util.routing import redirect_unless_target


def course(request, course_id):
    try:
        return render_with_default(
            request,
            'course/info.html',
            _course_context(request, course_id)
        )
    except Course.DoesNotExist:
        return db_error('Requested course does not exist.')


def _course_context(request, course_id):

    if isinstance(course_id, Course):
        active_course = course_id
        course_id = course_id.id
    else:
        active_course = Course.objects.get(id=course_id)

    participants_count, max_participants = active_course.saturation_level
    sub_name = active_course.subject.name
    context = {
        'title': sub_name,
        'course_id': course_id,
        'course': active_course,
        'backurl': reverse('subject', args=[sub_name]),
        'participants_count': participants_count,
        'max_participants': max_participants,
        'course_is_active': active_course.active,
    }
    user = request.user

    if user.is_authenticated():

        context['is_subbed'] = user.student.course_set.filter(id=course_id).exists()

        if active_course.is_teacher(user):
            context['is_teacher'] = True
            context['students'] = active_course.participants.all()

    return context


@needs_teacher_permissions
def edit_course(request, course_id):
    try:
        current_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error('Requested course does not exist.')

    if request.method == "POST":

        form = EditCourseForm(request.POST)

        if form.is_valid():

            cleaned = form.cleaned_data

            for prop in filter(cleaned.__contains__,(
                'active',
                'max_participants'
            )):

                current_course.__setattr__(prop,cleaned[prop])

            if 'description' in cleaned:
                current_course.description = cleaned['description']

            current_course.save()
            return redirect('course', course_id)

    else:
        form = EditCourseForm({
                'active': current_course.active,
                'description': current_course.description,
                'max_participants': current_course.max_participants
            })

    return render_with_default(
        request,
        'course/edit.html',
        {
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
        return db_error('Requested course does not exist.')

    curr_course.active = active
    curr_course.save()
    return redirect('course', course_id)


@permission_required('course.add_course')
def create(request):

    if request.method == 'POST':
        form = CreateCourseForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data

            active = cleaned.get('active', False)

            try:
                created = Course.objects.create(
                    schedule=Schedule.objects.create(_type=cleaned['schedule']),
                    active=active if active is not None else False,
                    subject=Subject.objects.get(id=int(cleaned['subject'])),
                    max_participants=cleaned['max_participants'],
                    description=cleaned['description']
                )
            except Subject.DoesNotExist:
                return db_error(
                    'The subject entered does not exist. This error should never occur, please try again. '
                    'Should the error repeat please contact an administrator and include the following url "{}".'
                    ''.format(request.path)
                )

            created.teacher.add(request.user.student)

            return redirect('course', created.id)
    else:
        form = CreateCourseForm()

    return render_with_default(request, 'course/create.html', {'form': form})


@needs_teacher_permissions
def add_teacher(request, course_id):
    context = {'course_id': course_id, 'target': reverse('add-teacher', args=(course_id,))}

    try:
        curr_course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error('This course does not exist ... ')

    if request.method == 'POST':
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(username=form.cleaned_data['username'])

                curr_course.teacher.add(user.student)

                return redirect('add-teacher', course_id)
            except User.DoesNotExist:
                context['error'] = 'The username you entered does not exist in my database, sorry :('
    else:
        form = AddTeacherForm()

    context['form'] = form
    context['teachers'] = curr_course.teacher

    return render_with_default(
        request,
        'course/teacher.html',
        context
    )


@needs_teacher_permissions
@require_POST
def remove_teacher(request, course_id, teacher_id):
    try:
        Course.objects.get(id=course_id).teacher.remove(Student.objects.get(id=teacher_id))
    except Course.DoesNotExist:
        return db_error('This course does not exist.')
    except Student.DoesNotExist:
        return db_error('This student does not exist.')
    return redirect_unless_target(request, 'course', course_id)
