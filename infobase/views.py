import calendar
import datetime
import django.newforms as forms
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response
from django.views.decorators.cache import cache_page
from infobase.models import Course, ClassMeeting, Flag, Person, Room, Scan, phase_for_cohort_and_date
from infobase.models import SECTIONS, SECTION_CHOICES, STUDENT_KIND, FACULTY_KIND

def _calendar_data(mode="report", date=None):
    today = datetime.date.today()
    if not date:
        date = today
    month = calendar.monthcalendar(date.year, date.month)
    weeks = [[day or '' for day in week] for week in month]
    if date.year == today.year and date.month == today.month:
        highlight_day = today.day
    return {
        'month': calendar.month_name[date.month], 
        'year': date.year, 
        'weeks': weeks, 
        'daynames': calendar.day_abbr,
        'url_base': "/%s/%4d/%02d/" % (mode, date.year, date.month),
        'today': highlight_day or None
        }
        
def scan(request):
    """Process a scan"""
    if request.method == 'POST':
        id_number = request.POST['id_number']
        try:
            person = Person.objects.get(id_number=id_number)
        except Person.DoesNotExist:
            warning = "ID number not found!"
            return render_to_response("scan.html", locals())
        # we can just record a raw scan for now, but it would be nice
        # to figure out right here what class is meeting and add that to the "Scan" record
        timestamp = datetime.datetime.now()
        scan = Scan(person=person, timestamp=timestamp)
        scan.save()
        last_scan = scan
    return render_to_response("scan.html", locals())

@login_required
@cache_page(30)
def attendance(request, class_id=None, year=None, month=None, day=None):
    """On-screen attendance form for use by instructors"""
    cal = _calendar_data(mode="attendance")
    # Two different ways to get the list of classes: a specific day, or (default) today
    listdate = None
    if year and month and day:
        listdate = datetime.date(int(year), int(month), int(day))
    elif class_id == None:
        listdate = datetime.date.today()
    if listdate:
        classmeetings = [c for c in ClassMeeting.objects.filter(date=listdate) if not c.is_open()]
        return render_to_response("classlist.html", locals())
        
    # If no list, try to find a specific class by class_id
    try:
        theclass = ClassMeeting.objects.get(pk=class_id)
        if theclass.is_open():
            return HttpResponse("That's an open class -- no attendance taken.")
    except ClassMeeting.DoesNotExist:
        return HttpResponse("Can't find that class!")

    title = "Attendance for %s" % theclass
        
    # if this form was POSTed, it must be attendance data
    if request.method == "POST":
        for field, value in request.POST.items():
            if field.startswith("present_"):
                student_id = int(field[8:])
                student = Person.objects.get(pk=student_id)
                timestamp = datetime.datetime.now()  # TODO: should probably be official class start-time
                scan = Scan(person=student, timestamp=timestamp, classmeeting=theclass)
                scan.save()
        return HttpResponse("Attendance for <b>%s, Section %s</b> has been recorded. Thank you!<br><br><a href='/attendance/'>Back to class list</a>" % (theclass.course, theclass.section))
        
    # if we've reached this point, we have a GET request with a class_id
    students = Person.objects.section(theclass.section, theclass.date)
    return render_to_response("checklist.html", locals())

@login_required
def report(request, class_id=None, year=None, month=None, day=None, person_id=None):
    if person_id:
        person = Person.objects.get(id_number=person_id)
        if person.is_student():
            inclass = _where_is_section(person.section)
            try:
                last_scan = Scan.objects.filter(person=person).latest()
            except Scan.DoesNotExist:
                last_scan = None
            if not inclass:
                message = "Not scheduled for class"
        elif person.is_faculty():
            inclass = _where_is_instructor(person)
            if not inclass:
                message = "Not scheduled for class"
        return render_to_response("whereis.html", locals())
    if not class_id:
        listdate = datetime.date.today()
        if year and month and day:
            listdate = datetime.date(int(year), int(month), int(day))
        classmeetings = ClassMeeting.objects.filter(date=listdate)
        cal = _calendar_data()
        return render_to_response("classlist.html", dict(locals(), mode="report"))
    try:
        theclass = ClassMeeting.objects.get(pk=class_id)
    except ClassMeeting.DoesNotExist:
        return HttpResponse("Can't find that class!")
    present, absent = theclass.attendance()
    title = "Report for %s" % theclass
    return render_to_response("class_report.html", locals())

def _where_is_section(section):
    """If this section is in class right now, which class is it?"""
    date_time = datetime.datetime.now()
    try:
        theclass = ClassMeeting.objects.filter(
            section=section, 
            date=date_time.date(), 
            time_start__lte=date_time.time()
            ).order_by('-time_start')[0]
    except IndexError:
        return None
    return theclass.first_hour_classmeeting()
    
def _where_is_instructor(person):
    """If this instructor is in class right now, which class is it?"""
    classes_today = ClassMeeting.objects.filter(date=datetime.date.today())
    the_class = [c for c in classes_today 
        if c.has_started() and not c.is_over()
        and person in c.instructors.all()]
    if the_class:
        return the_class[0]

@login_required
@cache_page(60)
def status(request):
    scheduled_classes = []
    for section in SECTIONS:
        theclass = _where_is_section(section)
        if theclass:
            scheduled_classes.append((section, theclass))
    title = "Status"
    return render_to_response("status.html", locals())

@login_required
@cache_page(60)
def noshow(request):
    """List people who haven't been marked present recently"""
    today = datetime.date.today()
    noshows = []
    for days_back in range(7):
        date = today - datetime.timedelta(days=days_back)
        if date.isoweekday() < 6:   # don't show weekends
            not_seen = list(Person.objects.not_seen_since(date))
            mia_people = [p for p in not_seen if not p.is_on_leave(date)]
            loa_people = [p for p in not_seen if p.is_on_leave(date)]
            mia_people.sort(lambda a, b: cmp(a.section_ord(), b.section_ord()))
            loa_people.sort(lambda a, b: cmp(a.section_ord(), b.section_ord()))
            noshows.append((date, mia_people, loa_people))
    title = "No-Show Report"
    return render_to_response("noshows.html", locals())

@login_required
@cache_page(60)
def student_report(request, student_id=None, date=None):
    """Info on an individual student"""
    if student_id == None:
        students = Person.objects.enrolled()
        return render_to_response("student_report.html", locals())
    student = Person.objects.get(pk=student_id)
    section = student.section()
    if date == None:
        date = datetime.date.today()
    week_back = date- datetime.timedelta(days=7)
    meetings = ClassMeeting.objects.filter(
        date__gte=week_back, 
        date__lte=date, 
        section=section
        ).order_by('date', 'time_start')
    # TODO: should filter out classes that are in the future!
    report = []
    for meeting in meetings:
        if meeting.is_first_hour() and meeting.is_over():
            present, absent = meeting.attendance()
            report.append((meeting, "Present" if student in present else "Absent"))
    return render_to_response("student_report.html", locals())


@cache_page(300)
def faces(request, section=None):
    """Dynamic facesheet"""
    sections = SECTIONS
    if not section:
        people = Person.objects.enrolled()
        label = "Students"
    elif section == "employees":
        people = Person.objects.exclude(kind=Person.PEOPLE_TYPES_MAPPING['Student'])
        label = "Faculty and Staff"
    else:
        people = Person.objects.section(section)
        label = "Section %s" % section
        location = _where_is_section(section)
    title = "Faces"
    return render_to_response("faces.html", locals())

@login_required
def phone_list(request):
    """
    Return a complete list of student phone numbers, by section.  
    """
    today = datetime.date.today()
    people_raw = Person.objects.filter(kind__exact=STUDENT_KIND, id_expiry__gt=today)
    people = sorted(people_raw, key=lambda p: (p.section_ord(), p.lastname))
    return render_to_response("admin/phone_list.html", locals())

@login_required
def schedule(request):
    """
    Display a schedule for the day.
    """
    classes_today = ClassMeeting.objects.filter(date=datetime.date.today())
    classmeetings = sorted(classes_today, key=lambda c: (c.time_start, c.section_ord()))
    return render_to_response("schedule.html", locals())
    
@login_required
def flagged_people(request, flag_name):
    """List all people who have the named flag set."""
    if flag_name:
        try:
            flag = Flag.objects.get(label=flag_name)
            title = "%s List" % flag
        except Flag.DoesNotExist:
            raise Http404
        people = flag.person_set.all()
    else:
        # No flag specified, so offer a list of all flags that are in use
        flags = [f for f in Flag.objects.all() 
            if f.person_set.count() 
            and f.label.lower() != "test"]
    return render_to_response("flagged_people.html", locals())


class ScheduleBuilderForm(forms.Form):
    _courses = [(c.id, str(c)) for c in Course.objects.filter(current=True)]
    _hours = [(x, "%s:00" % (x % 12)) for x in [8,9,10,11,13,14,15,16]]
    _lengths = [(x, "%s hours" % x) for x in [1,2,3,4]]
    _instructors = [(p.instructor_letter, str(p)) for p in Person.objects.filter(kind=FACULTY_KIND)]
    _rooms = [(r.id, str(r)) for r in Room.objects.all()]
    course = forms.ChoiceField(choices=_courses)
    start_time = forms.ChoiceField(choices=_hours)
    length = forms.ChoiceField(choices=_lengths)
    room = forms.ChoiceField(choices=_rooms)
    sections = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=SECTION_CHOICES)
    instructors = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=_instructors, required=False)


def _create_classmeetings(data, date):
    """
    From the provided data (a form submission), build a list of ClassMeeting objects
    and return them.
    """
    course = Course.objects.get(id=int(data['course']))
    start_time = int(data['start_time'])
    length = int(data['length'])
    instructors = Person.objects.instructors(data['instructors'])
    room = Room.objects.get(id=int(data['room']))
    for hour in range(start_time, start_time + length):
        time = datetime.time(hour, 0)
        for section in data['sections']:
            # Find conflicts. Could be streamlined with Q objects, adding instructor check
            conflicts = ClassMeeting.objects.filter(date=date, time_start=time, section=section).count()
            conflicts += ClassMeeting.objects.filter(date=date, time_start=time, room=room).count()
            if conflicts:
                raise ValueError, "Conflict found with submitted classmeetings"
            meeting = ClassMeeting(date=date, time_start=time, course=course, room=room, section=section)
            print "Saving", meeting
            meeting.save()
            for instructor in instructors:
                meeting.instructors.add(instructor)
    return True

@login_required
def schedule_builder(request, datestring):
    """
    Interface for constructing schedules, replacing the old Excel -> CSV -> pipeline
    """
    schedule_date = None
    if datestring:
        schedule_date = datetime.datetime.strptime(datestring, "%Y-%m-%d")
        
    if request.method == "POST":
        submitted_form = ScheduleBuilderForm(request.POST)
        if submitted_form.is_valid():
            data = submitted_form.cleaned_data
            _create_classmeetings(data, schedule_date)
    elif request.method == "GET":
        builder_form = ScheduleBuilderForm()
        if not schedule_date:
            today = datetime.date.today()
            date_choices = []
            for ahead in range(1, 90):
                date = today + datetime.timedelta(days=ahead)
                if date.isoweekday() == 1:
                    date_choices.append(date)
    if schedule_date:
        schedule_days = []
        for weekday in range(5):
            classmeetings = ClassMeeting.objects.filter(date=schedule_date + datetime.timedelta(days=weekday))
            schedule_lines = sorted(classmeetings, key=lambda c: (c.time_start, c.section_ord()))
            schedule_days.append(schedule_lines)
            if schedule_date.isoweekday() == 1:
                date_choices = [schedule_date+datetime.timedelta(days=ahead) for ahead in range(1,5)]
            
    return render_to_response("admin/schedule_builder.html", locals())
    
# API views

def students_api(request):
    """
    Return Person data for all students, in JSON format.
    """
    # No custom filters yet, but could be passed via request.GET and parsed here
    filters = {}  
    filters.update({'kind': STUDENT_KIND})
    students = Person.objects.filter(**filters)
    data = serializers.serialize("json", students)
    return HttpResponse(data, mimetype="application/json")
