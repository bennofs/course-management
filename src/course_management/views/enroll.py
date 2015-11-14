from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_POST
from django.shortcuts import redirect


from course_management.views.base import render_with_default
from course_management.models.course import Course
from util.error.reporting import db_error
from util.routing import redirect_unless_target
from .course import _course_context


@require_POST
@login_required()
def add(request, course_id):
    user = request.user
    stud = user.student
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error('Requested course does not exist.')
    ps = course.participants
    session = request.session

    if ps.filter(id=user.id).exists():
        session['enroll-error'] = 'You are already enrolled in this course.'
    elif ps.count() >= course.max_participants:
        session['enroll-error'] = 'Sorry, this course is full.'
    else:
        if 'enroll-error' in session:
            del session['enroll-error']
        ps.add(stud)

    # redirect to course overview or specified target
    return redirect_unless_target(request, 'unregister-course-done', course_id)


@require_POST
@login_required()
def remove(request, course_id):
    stud = request.user.student
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error('Requested course does not exist.')
    ps = course.participants
    ps.remove(stud)

    # redirect to course overview or specified target
    return redirect_unless_target(request, 'register-course-done', course_id)


@login_required()
def enroll_response(request, course_id, action=None):
    session = request.session
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return db_error('Requested course does not exist.')
    context = _course_context(request, course)
    context['action'] = action
    context['subject'] = course.subject.name
    context['course_id'] = course_id

    if 'enroll-error' in session:
        context['error'] = session['enroll-error']
        del session['enroll-error']
    return render_with_default(request, 'enroll/response.html', context)
