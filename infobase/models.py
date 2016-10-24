"""
Models file for Hallmark infobase

This describes the data structures for all student, staff, and class attendance data.

Django 1.x note: Model methods that return HTML for clickable shortcuts 
will need to use the `django.utils.safestring.mark_safe()` method.

Some tests/examples:

>>> p = Person(firstname="Pat", lastname="Patson")
>>> p.save()   # saving triggers the auto-fill of preferred_firstname
>>> p.preferred_firstname
'Pat'
>>> p.is_student()
True
>>> p.is_faculty()
False
>>> p.is_employee()
False
>>> p.is_active()
True

>>> p.student_sec_phase1 = "T"
>>> p.save()
>>> DATE_IN_PHASE_1 = dict(PHASE_END_DATES)[1][1]
>>> p.section(DATE_IN_PHASE_1)
'T'
>>> list(Person.objects.section("T", date=DATE_IN_PHASE_1))
[<Person: Pat Patson>]

>>> p.id_expiry = datetime.date(2001,1,1)
>>> p.is_enrolled()  # ID expired in 2001
False
>>> last_day = datetime.date(2099,1,1)
>>> p.id_expiry = last_day
>>> p.is_enrolled()  # is enrolled for a very long time!
True
>>> p.is_enrolled(last_day)  # until the day their ID expires
False

The "inclusive" flag is for attendance reports.
>>> p.save()  # For tests of managers, data needs to be saved
>>> Person.objects.enrolled(date=last_day)
[]
>>> Person.objects.enrolled(date=last_day, inclusive=True)
[<Person: Pat Patson>]

>>> phod999 = Course(course_number="PHO-D 999", schedule_name="Digital Hoohah")
>>> phod999
<Course: PHO-D 999: Digital Hoohah>
>>> phod999.save()

>>> q = Person(firstname="Quimby", preferred_firstname="Guest", lastname="Instructor", kind=2, id_number="1000666", instructor_letter="Q")
>>> q
<Person: Guest Instructor>
>>> q.is_faculty()
True
>>> q.save()
>>> Person.objects.instructors("Q")
[<Person: Guest Instructor>]
>>> Person.objects.all()
[<Person: Guest Instructor>, <Person: Pat Patson>]

>>> r = Room.objects.create()
>>> aclass = ClassMeeting.objects.create(course=phod999, 
...    section="T", room=r, date=DATE_IN_PHASE_1, 
...    time_start=datetime.time(8,0,0))
>>> aclass.instructors.add(q)
>>> aclass
<ClassMeeting: Digital Hoohah, 8:00 AM 2009-11-06>
>>> aclass.is_first_hour()
True
>>> aclass.previous_hour_classmeeting() is None
True
>>> aclass.datetime_start() < aclass.datetime_end()
True
>>> aclass.is_open()
False
>>> aclass.is_all_school()
True
>>> aclass_hour2 = ClassMeeting.objects.create(course=phod999, 
...    section="T", room=r, date=DATE_IN_PHASE_1, 
...    time_start=datetime.time(9,0,0))
>>> aclass_hour2.is_not_first_hour()
True
>>> aclass_hour2.previous_hour_classmeeting()
<ClassMeeting: Digital Hoohah, 8:00 AM 2009-11-06>
>>> aclass.next_hour_classmeeting()
<ClassMeeting: Digital Hoohah, 9:00 AM 2009-11-06>
>>> aclass.number_of_hours()
2
>>> aclass_repeat = ClassMeeting.objects.create(course=phod999, 
...    section="T", room=r, date=DATE_IN_PHASE_1, 
...    time_start=datetime.time(13,0,0))

# Noncontiguous hours should not be counted together
>>> aclass.number_of_hours()
2
>>> aclass_repeat.number_of_hours()
1

>>> s = Scan(person=p, classmeeting=aclass)
>>> s.save()
>>> s
<Scan: Pat Patson, Digital Hoohah, 8:00 AM 2009-11-06>
>>> list(aclass.scan_set.all())
[<Scan: Pat Patson, Digital Hoohah, 8:00 AM 2009-11-06>]
>>> aclass.attendance()   # Fetch tuple of present, absent lists
([<Person: Pat Patson>], [])
>>> p.id_expiry = PHASE_END_DATES[1][4]
>>> p.save()
>>> aclass.attendance()
([<Person: Pat Patson>], [])
>>> s.delete()
>>> aclass.attendance()   # Without the scan, Pat is absent
([], [<Person: Pat Patson>])

Finally, restore that deleted scan, since it's used by other doctests below
>>> s = Scan(person=p, classmeeting=aclass)
>>> s.save()

"""

import datetime
import os
from django.conf import settings
from django.db import models

SECTIONS = "TRIPODS"
SECTION_CHOICES = zip(SECTIONS, SECTIONS)
STUDENT_KIND, STAFF_KIND, FACULTY_KIND = 0, 1, 2

# Each cohort has its own phase calendar.
# End of Phase 4 is the end of the academic year (i.e. normal ID expiry)
PHASE_END_DATES = { 1: { 1: datetime.date(2009, 11, 6), 
                         2: datetime.date(2010, 1, 15), 
                         3: datetime.date(2010, 3, 26), 
                         4: datetime.date(2010, 6, 18) },
                    2: { 1: datetime.date(2010, 3, 12),
                         2: datetime.date(2010, 5, 21),
                         3: datetime.date(2010, 7, 30),
                         4: datetime.date(2010, 10, 22) }}


def one_week_ago():
    """Helper function for use in limit_choices_to"""
    return datetime.date.today() - datetime.timedelta(7)


def phase_for_cohort_and_date(cohort, date=None):
    """
    Return an integer representing the phase for the given cohort on the given date.
    
    >>> phase_for_cohort_and_date(1, datetime.date(2009, 9, 1))
    1
    >>> phase_for_cohort_and_date(1, datetime.date(2010, 6, 1))
    4
    >>> phase_for_cohort_and_date(1, datetime.date(2099, 1, 1)) == None
    True
    """
    result = None
    phase_dates = sorted(PHASE_END_DATES[cohort].items(), reverse=True)
    for phase_num, end_date in phase_dates:
        if date <= end_date:
            result = phase_num
    return result


class Flag(models.Model):
    """Special status flags (mostly for student records, e.g. night managers)"""
    label = models.CharField(maxlength=30, help_text="A short name for the flag that will appear in the Flag list.")
    description = models.TextField(blank=True, help_text="Internal description to remind you what this flag is for.")
    
    class Meta:
        ordering = ["label"]

    class Admin:
        pass

    def __str__(self):
        return self.label


class PersonManager(models.Manager):
    """
    Custom manager methods for the Person class.

    By default, on their id_expiry date students are no longer considered
    enrolled. The "inclusive" flag redefines enrollment to include the expiry
    date. (This flag is used by some attendance reporting code).

    Examples (some of which depend on data saved from doctests at top of file):
    >>> Person.objects.instructors("Q")
    [<Person: Guest Instructor>]
    >>> DATE1 = dict(PHASE_END_DATES)[1][1]
    >>> DATE5 = DATE1 + datetime.timedelta(365)  # Phase 5, as we say
    >>> Person.objects.enrolled(date=DATE1)
    [<Person: Pat Patson>]
    >>> Person.objects.section("T", date=DATE1)
    [<Person: Pat Patson>]
    >>> Person.objects.not_seen_since(DATE1)   # Pat has scanned since end of Phase 1
    []
    """
    def section(self, letter, date=None, inclusive=False):
        """Return students in section as of date (today if unspecified)"""
        section_people = sorted(s for s in self.enrolled(date=date, inclusive=inclusive) if s.section(date) == letter)
        return section_people

    def instructors(self, letters):
        """Return Person objects matching instructor letters -- used by CSV schedule import"""
        instructors = []
        for letter in letters:
            instructors.append(self.get(instructor_letter=letter))
        return instructors

    def enrolled(self, date=None, inclusive=False):
        """Return students enrolled as of date (today if unspecified)"""
        if date == None:
            date = datetime.date.today()
        if inclusive:
            return self.filter(kind=STUDENT_KIND, id_expiry__gte=date)
        else:
            return self.filter(kind=STUDENT_KIND, id_expiry__gt=date)            

    def not_seen_since(self, date):
        """Return all the people who have not scanned since the given date"""
        seen = self.filter(scan__timestamp__gte=date).distinct().values('id')
        not_seen = self.enrolled(date).exclude(id__in=[v['id'] for v in seen])
        return not_seen


class Person(models.Model):
    """
    A Hallmark student or employee
    
    >>> s = Person(firstname="Bob", preferred_firstname="Bob", lastname="Dobbs")
    >>> s
    <Person: Bob Dobbs>
    >>> s.is_active()  # No id_expiry set, so he should be active (like staff)
    True
    >>> s.id_expiry = datetime.date.today() - datetime.timedelta(days=1)
    >>> s.is_active()
    False
    >>> s.id_expiry = datetime.date.today() + datetime.timedelta(days=1)
    >>> s.is_active()
    True
    >>> s.is_on_leave()
    False
    >>> s.loa_start = datetime.date(2001,1,1)
    >>> s.loa_end = datetime.date(2001,1,10)
    >>> d1 = datetime.date(2001,1,2)
    >>> d2 = datetime.date(2001,1,11)
    >>> s.is_on_leave(date=d1)
    True
    >>> s.is_on_leave(date=d2)
    False
    """
    PEOPLE_TYPES = [(STUDENT_KIND, "Student"), (STAFF_KIND, "Staff"), (FACULTY_KIND, "Faculty")]
    PEOPLE_TYPES_MAPPING = dict((n, t) for (t, n) in PEOPLE_TYPES) 
    COHORT_CHOICES = [(1, "September"), (2, "January")] 
    
    kind = models.IntegerField(choices=PEOPLE_TYPES, default=0)
    firstname = models.CharField(max_length=100)
    preferred_firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    id_number = models.CharField(blank=True, max_length=10, unique=True)
    id_expiry = models.DateField(blank=True, null=True)
    primary_phone = models.CharField(blank=True, max_length=15, help_text="Where the person is mostly likely to be found.")
    secondary_phone = models.CharField(blank=True, max_length=15)
    permanent_phone = models.CharField(blank=True, max_length=15, help_text="Parents or other non-Hallmark home phone number.")
    date_of_birth = models.DateField(blank=True, null=True)
    email = models.EmailField(blank=True)
    flags = models.ManyToManyField(Flag, blank=True)
    # STUDENT fields
    student_cohort = models.SmallIntegerField(blank=True, null=True, default=1, choices=COHORT_CHOICES)
    student_home_city = models.CharField(blank=True, max_length=100)
    student_home_state = models.CharField(blank=True, max_length=30)
    student_home_country = models.CharField(blank=True, max_length=30)
    student_address_1 = models.CharField(blank=True, max_length=100)
    student_address_2 = models.CharField(blank=True, max_length=100)
    student_city = models.CharField(blank=True, max_length=100)
    student_state = models.CharField(blank=True, max_length=2)
    student_zip = models.CharField(blank=True, max_length=10)
    student_sec_phase1 = models.CharField(blank=True, max_length=1, choices=SECTION_CHOICES)
    student_sec_phase2 = models.CharField(blank=True, max_length=1, choices=SECTION_CHOICES)
    student_sec_phase3 = models.CharField(blank=True, max_length=1, choices=SECTION_CHOICES)
    student_sec_phase4 = models.CharField(blank=True, max_length=1, choices=SECTION_CHOICES)
    loa_start = models.DateField(blank=True, null=True, help_text="Leave of Absence start date; leave blank if not on LOA")
    loa_end = models.DateField(blank=True, null=True, help_text="Leave of Absence end date; leave blank if not on LOA")
    # STAFF/FACULTY Fields
    staff_alpha_id = models.CharField(max_length=50, blank=True)
    staff_work_phone = models.CharField(max_length=20, blank=True)
    staff_work_extension = models.CharField(max_length=4, blank=True)
    staff_instant_messaging = models.CharField(max_length=50, blank=True)
    instructor_letter = models.CharField(blank=True, max_length=1)

    objects = PersonManager()   # the default manager; used by admin

    class Admin:
        list_display = ('__unicode__', 'id_number', 'kind', 'section')
        list_filter = ('kind', 'student_cohort', 'student_sec_phase1', 'student_sec_phase2', 
            'student_sec_phase3', 'student_sec_phase4', 'flags')
        search_fields = ('firstname', 'preferred_firstname', 'lastname', 'email', 'id_number')
        fields = (
            ("General Information", {'fields': ("kind", "firstname", "preferred_firstname", "lastname", "id_number", "id_expiry", "primary_phone", "secondary_phone", "permanent_phone", "date_of_birth", "email")}),
            ("Student Information", {'fields': ("student_cohort", "student_home_city", "student_home_state", "student_home_country", "student_address_1", "student_address_2", "student_city", "student_state", "student_zip", "student_sec_phase1", "student_sec_phase2", "student_sec_phase3", "student_sec_phase4", "loa_start", "loa_end", "flags")}),
            ("Staff/Faculty Information", {'fields': ("staff_alpha_id", "staff_work_phone", "staff_work_extension", "staff_instant_messaging", "instructor_letter")}),
            )

    class Meta:
        verbose_name_plural = "people"
        ordering = ["lastname", "firstname", "kind"]

    def __unicode__(self):
        return u"%s %s" % (self.preferred_firstname, self.lastname)

    def __cmp__(self, other):
        if self.lastname == other.lastname:
            return cmp(self.preferred_firstname, other.preferred_firstname)
        else:
            return cmp(self.lastname, other.lastname) 

    def save(self):
        if not self.preferred_firstname:
            self.preferred_firstname = self.firstname
        if self.kind == STUDENT_KIND and not self.id_expiry:
            self.id_expiry = PHASE_END_DATES[self.student_cohort][4] + datetime.timedelta(days=7)
        super(Person, self).save() 

    def is_active(self):
        if self.id_expiry:
            return self.id_expiry > datetime.date.today()
        else:
            return True

    def is_student(self):
        return self.kind == STUDENT_KIND
        
    def is_employee(self):
        return self.kind in (STAFF_KIND, FACULTY_KIND)
        
    def is_faculty(self):
        return self.kind == FACULTY_KIND

    def is_enrolled(self, date=None):
        if date is None:
            date = datetime.date.today()
        return self.is_student() and date < self.id_expiry	

    def is_on_leave(self, date=None):
        if date is None:
            date = datetime.date.today()
        if self.loa_start and self.loa_end:
            return self.loa_start <= date <= self.loa_end
        else:
            return False
        
    def section(self, date=None):
        """
        Student's section as of date (or today if no date is given)
        """
        if not self.is_student():
            return None
        if not date:
            date = datetime.date.today()
        section = ""
        if phase_for_cohort_and_date(self.student_cohort, date):
            section = getattr(self, "student_sec_phase%d" % phase_for_cohort_and_date(self.student_cohort, date))
        return section

    def section_ord(self, date=None):
        """
        Ordinal value of student's section, for use in sorting.
        """
        try:
            return SECTIONS.index(self.section(date))
        except ValueError:  # Handle obsolete section letters (B,A,C,K)
            return None
         
    def get_admin_url(self):
        """Direct link to this person's page in the admin"""
        return "/admin/infobase/person/%s/" % self.id

    def id_photo_url(self):
        """Relative URL to ID photo JPEG"""
        src = "faces/%s.jpg" % self.id_number
        path = os.path.join(settings.MEDIA_ROOT, src)
        if os.path.exists(path):
            return os.path.join(settings.MEDIA_URL, src)
        else:
            return os.path.join(settings.MEDIA_URL, "faces/no_photo.jpg")
        
    def happy_birthday(self):
        """Is it this person's birthday?"""
        today = datetime.date.today()
        bd = self.date_of_birth
        return (today.month, today.day) == (bd.month, bd.day)
        
    def flagged(self, flag_label):
        """Is this person flagged with the named flag?"""
        return bool(self.flags.filter(label=flag_label).count())

    def whereis_url(self):
        """URL for 'whereis' screen for this person"""
        return "/report/whereis/%s/" % self.id_number


class Vehicle(models.Model):
    """Vehicles (for students today, but someday we may require staff permits too)"""
    owner = models.ForeignKey(Person)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.IntegerField(blank=True, null=True)
    color = models.CharField(blank=True, max_length=20)
    plate_number = models.CharField(blank=True, max_length=10)
    plate_state = models.CharField(blank=True, max_length=3)
    permit_number = models.CharField(blank=True, max_length=20)
    note = models.CharField(blank=True, max_length=255)

    class Admin:
        list_display = ["__unicode__", "person_link", "plate_state", "plate_number"]
        search_fields = ["make", "model", "plate_number", "permit_number", "note"]
        list_filter = ["make", "plate_state", "color"]

    def __unicode__(self):
        return u"%s %s %s %s" % (self.color, self.year, self.make, self.model)

    def person_link(self):
        """HTML link to make it easier to go from vehicle lookup to contact"""
        return "<a href='%s'>%s</a>" % (self.owner.get_admin_url(), self.owner)
    person_link.allow_tags = True


class Course(models.Model):
    """
    A course is a curriculum topic, a category that ClassMeetings belong to.
    """
    course_number = models.CharField(blank=True, max_length=10)
    schedule_name = models.CharField(blank=False, max_length=100)
    default_lead_instructor = models.ForeignKey(Person, 
        limit_choices_to={'kind': 2}, blank=True, null=True)
    current = models.BooleanField(default=True, help_text="")
    # long_name = models.CharField(blank=True, max_length=200)  ## TODO: drop this column
    # description = models.TextField(blank=True)  ## TODO: drop this column
    
    class Admin:
        list_display = ["course_number", "schedule_name", "default_lead_instructor"]
        search_fields = ["long_name", "schedule_name", "course_number"]
        list_filter = ["current"]

    class Meta:
        ordering = ["-current", "course_number", "schedule_name"]

    def __unicode__(self):
        return u"%s: %s" % (self.course_number, self.schedule_name)
        

class Room(models.Model):
    """
    Rooms have an abbreviation used in the spreadsheet, and a full_name
    (perhaps longer) name which is used for display within the attendance 
    system. If no full_name is provided, the abbreviation is used.
    
    >>> r = Room(abbreviation="PS-7")
    >>> r
    <Room: >
    >>> r.save()
    >>> r
    <Room: PS-7>
    >>> r.full_name = "Top Secret Portrait Studio"
    >>> r
    <Room: Top Secret Portrait Studio>
    """
    abbreviation = models.CharField(blank=True, max_length=100)
    full_name = models.CharField(blank=True, max_length=100)

    class Admin:
        list_display = ["full_name", "abbreviation"]
        search_fields = ["full_name", "abbreviation"]

    class Meta:
        ordering = ["full_name"]

    def __unicode__(self):
        return self.full_name

    def save(self):
        if self.abbreviation and not self.full_name:
            self.full_name = self.abbreviation
        super(Room, self).save()

class ClassMeeting(models.Model):
    """
    An individual occurrence of a particular Course.
    """
    course = models.ForeignKey(Course)
    date = models.DateField(blank=True, null=True)
    time_start = models.TimeField(blank=True, null=True)
    time_end = models.TimeField(blank=True, null=True)
    instructors = models.ManyToManyField(Person,
        limit_choices_to={'kind': 2}, blank=True)
    room = models.ForeignKey(Room, blank=True)
    section = models.CharField(blank=True, max_length=1, choices=SECTION_CHOICES)

    class Meta:
        verbose_name = "class meeting"
        ordering = ["date", "time_start", "course", "section"]
        get_latest_by = "date` DESC, `time_start"  # Note: SQL injection hack

    class Admin:
        list_display = ["course", "date", "time_start", "section", "room", "instructor_list"]
        list_filter = ["room", "date", "section", "course"]
        search_fields = ["course", "instructors"]
        date_hierarchy = "date"

    def __unicode__(self):
        return u"%s, %s %s" % (
            self.course.schedule_name, 
            self.time_start.strftime("%I:%M %p").lstrip("0"), 
            self.date)

    def lead_instructor(self):
        """Lead instructor"""
        return self.instructors[0]
        
    def instructor_list(self):
        return ", ".join(str(i) for i in self.instructors.all())
        
    def get_attendance_url(self):
        return "/attendance/%s/" % self.id
        
    def get_report_url(self):
        return "/report/%s/" % self.id

    def report_header(self):
        """Header line for plaintext reports"""
        result = "%s %s, %s %s, Section %s" % (
            self.course.course_number, 
            self.course.schedule_name,
            self.date,
            "%d:%02d" % (self.time_start.hour, self.time_start.minute),
            self.section)
        return result
        
    def number_of_hours(self):
        """
        Length of this classmeeting in hours (used in attendance reporting).
        """
        class_length = 0
        class_continues = self.first_hour_classmeeting()  # Count from first hour
        while class_continues:
            class_length += 1
            class_continues = class_continues.next_hour_classmeeting()
        if not 0 < class_length < 9:
            raise RuntimeError, "Class length calculation error: %s == %s hours?" % (self, class_length)
        return class_length        
    
    def is_not_first_hour(self):
        return bool(self.previous_hour_classmeeting())

    def is_first_hour(self):
        return not self.is_not_first_hour()

    def first_hour_classmeeting(self):
        proceed = True
        theclass = self
        while proceed and theclass.is_not_first_hour():
            theclass = proceed = theclass.previous_hour_classmeeting()
        return theclass

    def previous_hour_classmeeting(self):
        return self.adjacent_hour_classmeeting(step=-1)

    def next_hour_classmeeting(self):
        return self.adjacent_hour_classmeeting(step=1)
        
    def adjacent_hour_classmeeting(self, step=None):
        """
        Return the ClassMeeting object representing the previous or next hour of this class,
        if any. `step` is -1 for previous hour (default), +1 for next hour. If no 
        ClassMeeting object is found, return `None`.
        """
        step = step/abs(step)  # Don't allow multi-hour steps
        adjacent_cm_start = datetime.time(self.time_start.hour + step, self.time_start.minute)
        if self.time_start.hour + step == 12:
            adjacent_cm_start = datetime.time(self.time_start.hour + 2 * step, self.time_start.minute)
        try:
            result = ClassMeeting.objects.get(
                section=self.section,
                course=self.course,
                date=self.date,
                time_start=adjacent_cm_start)
        except ClassMeeting.DoesNotExist:
            result = None
        return result
    
    def datetime_start(self):
        """A datetime object for this class's start."""
        return datetime.datetime.combine(self.date, self.time_start)
    
    def datetime_end(self):
        """
        A datetime object for this class's end.
        If it doesn't have an end time, we guess and store temporarily.
        """
        if not self.time_end:
            self.time_end = datetime.time(self.time_start.hour + 1, self.time_start.minute)
        return datetime.datetime.combine(self.date, self.time_end)

    def is_over(self):
        """Has this class ended (as of the time this method is called)?"""
        return self.datetime_end() < datetime.datetime.now()

    def has_started(self):
        """Has the time_start of this class passed (as of the time this method is called)?"""
        return self.datetime_start() < datetime.datetime.now()
        
    def is_open(self):
        """Is this class an "open" class where no attendance is taken?"""
        return self.instructors.count() == 0
        
    def attendance(self):
        """
        Return attendance lists (present, absent) for this class.
        """
        expected = Person.objects.section(self.section, date=self.date)
        present_raw = sorted(s.person for s in self.scan_set.all())
        present = []
        for p in present_raw:
            if p not in present:
                present.append(p)
        absent = [p for p in expected if p not in present]
        return (present, absent)

    def section_ord(self):
        """
        Ordinal value of ClassMeeting's section, for use in sorting.
        """
        try:
            return SECTIONS.index(self.section)
        except ValueError:  # Handle obsolete section letters (B,A,C,K)
            return None

    def is_all_school(self):
        """
        Is this classmeeting part of an all-school meeting?
        """
        this = self.first_hour_classmeeting()
        other_courses_at_same_time = ClassMeeting.objects.filter(
            time_start=this.time_start, date=this.date).exclude(course=this.course)
        return other_courses_at_same_time.count() == 0

    
    @classmethod
    def from_signout_data(cls, date, classtring, timestring, section):
        """
        This processes data from the logfile that comes in like this:
        
        2008-01-21T23:21:57-08:00,"Brad", "Bucksky", "beb4311@yahoo.com", "2008121", "T", "Portrait Studio", "01-22-2008", "morning", "P3 M-6"
        
        And is processed by the signout_log_processor.py script into a structured form.
        """
        if timestring == "morning":
            time_start = datetime.time(8,0,0)
        elif timestring == "afternoon":
            time_start = datetime.time(13,0,0)
        else:
            raise ValueError, "Improper time specified"
        return cls.objects.get(
            date=date, 
            course__schedule_name__startswith=classtring, 
            time_start=time_start,
            section=section,
            )


class ScanManager(models.Manager):
    """
    Custom manager to return only non-signout scans only.
    """
    def get_query_set(self):
        """The 'objects' queryset should not contain signouts"""
        return super(ScanManager, self).get_query_set().filter(is_signout=False)

class SignoutScanManager(models.Manager):
    """
    Custom manager to return signout scans only.
    """
    def get_query_set(self):
        """The 'objects' queryset should not contain signouts"""
        return super(SignoutScanManager, self).get_query_set().filter(is_signout=True)



class Scan(models.Model):
    """
    An individual instance of a student being marked present, or scanning.
    
    >>> some_student = Person.objects.filter(kind=0)[0]
    >>> then = datetime.datetime(2009, 1, 1, 1, 1, 1)
    >>> s = Scan(person=some_student, timestamp=then)
    >>> s.save()
    >>> s.is_signout
    False
    >>> so = Scan(person=some_student, timestamp=then, is_signout=True)
    >>> so.save()
    >>> so.is_signout
    True
    
    We should now have 3 scans total (one left over from earlier doctests):
    >>> len(Scan.admin_objects.all())
    3
    
    Two 'regular' scans, under the normal 'objects' manager:
    >>> len(Scan.objects.all())
    2
    
    And one signout scan:
    >>> len(Scan.signouts.all())
    1
    
    We should see only one scan for the class:
    >>> some_class = ClassMeeting.objects.all()[0]
    >>> Scan.objects.filter(classmeeting=some_class)[0].person
    <Person: Pat Patson>
    
    This should give the same result:
    >>> some_class.scan_set.all()[0].person
    <Person: Pat Patson>
    
    We should see only one "loose" scan:
    >>> Scan.barcode_scans_for_date(then.date())
    [<Scan: Pat Patson, 2009-01-01 01:01:01>]
    """
    person = models.ForeignKey(Person)
    timestamp = models.DateTimeField(default=datetime.datetime.now)
    classmeeting = models.ForeignKey(ClassMeeting, 
        blank=True, null=True,
        limit_choices_to={'date__gt': one_week_ago})
    is_signout = models.BooleanField(default=False)
    admin_objects = models.Manager()
    objects = ScanManager()
    signouts = SignoutScanManager()

    class Admin:
        list_display = ["precise_timestamp", "person_link", "classmeeting", "is_signout", "person_kind"]
        list_filter = ["timestamp", "is_signout", "person"]
        date_hierarchy = "timestamp"
        
    class Meta:
        ordering = ["-timestamp", "person"]
        get_latest_by = "timestamp"

    def __unicode__(self):
        if self.classmeeting:
            return unicode(u"%s, %s" % (self.person, self.classmeeting))
        else:
            return unicode(u"%s, %s" % (self.person, self.timestamp))

    def precise_timestamp(self):
        """
        The default representation of a DateTimeField doesn't include seconds, but it's
        useful to have them displayed.
        """
        return unicode(self.timestamp)

    def person_link(self):
        """HTML link to make it easier to go from scan to person"""
        return "<a href='%s'>%s</a>" % (self.person.get_admin_url(), self.person)
    person_link.allow_tags = True
    
    def person_kind(self):
        return self.person.get_kind_display()
    
    def report_line(self, format="%H:%M:%S"):
        return "* %s %s" % (self.person, self.timestamp.strftime(format))
        
    @classmethod
    def barcode_scans_for_date(cls, date):
        """
        Return all scans that happened on a given date, omitting 
        manual attendance entries -- in other words, scans that were
        done via barcode scanner.
        """
        next_day = date + datetime.timedelta(1)
        filters = {
            'timestamp__gte': date, 
            'timestamp__lt': next_day,
            'person__kind': STUDENT_KIND,
            }
        # Note: Raw SQL used here because 'classmeeting=None' in the ORM doesn't
        # give the needed result, yet we need to return a queryset 
        scans = cls.objects.filter(**filters).extra(where=["classmeeting_id is NULL"])
        return scans
