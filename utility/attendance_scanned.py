#!/usr/bin/env python
"""
Attendance reporting script for classes where attendance is taken by barcode scanner.
"""


import datetime
import doctest
import operator
import os
import sys
from optparse import OptionParser
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from django.core.mail import send_mail
from django.conf import settings
from infoserver.infobase.models import Course, ClassMeeting, Scan, Person, SECTIONS, STUDENT_KIND


scan_window_length = datetime.timedelta(minutes=30)


class Timespan(object):
    """
    Object representing a time span, a scanning time-window.
    
    >>> today = datetime.date.today()
    >>> t1 = Timespan(today, "07:30:00-08:00:00")
    >>> print t1
    7:30:00 AM - 8:00:00 AM
    
    >>> t2 = Timespan(today, "7:30-8:00")
    >>> t1 == t2
    True
    
    >>> print Timespan(today, "-9:00")
    8:30:00 AM - 9:00:00 AM
    >>> print Timespan(today, "16:50-")
    4:50:00 PM - 5:20:00 PM
    """
    def __init__(self, day, time_range):
        """
        Build a Timespan object based on strings describing time range.
        """
        start, end = time_range.split("-")
        # Allow omission of seconds
        if start.count(":") == 1:
            start += ":00"
        if end.count(":") == 1:
            end += ":00"
        # Allow omission of start or end time
        if start:
            hour_start, min_start, sec_start = map(int, start.split(":"))
            self.begin = datetime.datetime(day.year, day.month, day.day, hour_start, min_start, sec_start)
            if not end:
                self.end = self.begin + scan_window_length
        if end:
            hour_end, min_end, sec_end = map(int, end.split(":"))
            self.end = datetime.datetime(day.year, day.month, day.day, hour_end, min_end, sec_end)
            if not start:
                self.begin = self.end - scan_window_length
    
    def __cmp__(self, other):
        if self.begin != other.begin:
            return cmp(self.begin, other.begin)
        else:
            return cmp(self.end, other.end)
            
    def __str__(self):
        return "%s - %s" % (self.begin.strftime("%I:%M:%S %p").lstrip('0'), self.end.strftime("%I:%M:%S %p").lstrip('0'))


class Block(object): 
    """ 
    A time block representing an event, with two time-spans for
    scanning (start and end). Student must have a scan in both to be counted 
    present. The "blocks" list below contains one item for each block, with 
    both start and end windows.
    
    >>> date = datetime.date(1904, 1, 1)
    >>> course = Course(course_number="FOOBR1234", schedule_name="Digital Foobar")
    >>> b = Block(course, date, "7:30-8:00", "12:00-12:30")
    >>> print b
    Digital Foobar: 1904-01-01 08:00:00
    """
    def __init__(self, course, date, startspan, endspan):
        self.coursenum = course.course_number
        self.coursename = course.schedule_name
        self.date = date
        self.startspan = Timespan(date, startspan)
        self.endspan = Timespan(date, endspan)
        # Calculate length
        try:
            _cm = ClassMeeting.objects.filter(date=date, course=course)[0]
            self.length = _cm.number_of_hours()
        except ClassMeeting.DoesNotExist:
            self.length = 0
    
    def __str__(self):
        """Friendly string representation of this block"""
        return "%s: %s" % (self.coursename, self.startspan.end)

    
class ClassBlock(Block):
    """
    A block of time in which one course is attended by all sections. Scan in/out 
    times are assumed to be normal, i.e. class starts at :00 and ends at :50
    """
    def __init__(self, classmeeting):
        self.coursenum = classmeeting.course.course_number
        self.coursename = classmeeting.course.schedule_name
        self.date = classmeeting.date
        self.length = classmeeting.number_of_hours()

        _hour_start = classmeeting.time_start.hour
        scanin_begin = datetime.time(_hour_start - 1, 30)
        scanin_end = classmeeting.time_start
        scanout_begin = datetime.time(_hour_start + self.length - 1, 45)
        scanout_end = datetime.time(_hour_start + self.length, 15)

        self.startspan = Timespan(self.date, "%s-%s" % (scanin_begin, scanin_end))
        self.endspan = Timespan(self.date, "%s-%s" % (scanout_begin, scanout_end))


def last_scan_for_person(scan_set, person):
    """Return the last scan in the set for the given person."""
    scans_found = [s for s in scan_set if s.person == person]
    return scans_found[-1]


def scan_breakdown(block, options):
    scans = Scan.barcode_scans_for_date(date)
    students = Person.objects.enrolled(date, inclusive=True)
    if options.sections:
        students = [s for s in students if s.section() in options.sections]
    student_pks = set(p.id for p in students)

    scans_in = scans.filter(timestamp__gte=block.startspan.begin, timestamp__lte=block.startspan.end)
    people_scanned_in = set(s.person.id for s in scans_in)
    scans_out = scans.filter(timestamp__gte=block.endspan.begin, timestamp__lte=block.endspan.end)
    people_scanned_out = set(s.person.id for s in scans_out)
    present_people_pks = people_scanned_out & people_scanned_in
    present_people = Person.objects.enrolled(date, inclusive=True).filter(pk__in=list(present_people_pks))
    absent_people = Person.objects.filter(pk__in=list(student_pks - present_people_pks))

    classtime = block.startspan.end.strftime("%H:%M")
    output = ""
    for s in students:
        status = "present" if s in present_people else "absent"
        line = u"%s, %s, %s, %s, %s, %s, %s, %s, %s, %s\n" % (block.coursenum, block.coursename, date, classtime, s.section(block.date), block.length, s.id_number, s.lastname, s.preferred_firstname, status)
        output += line

    return output


def report(blocks, options):
    """Print an attendance report (in CSV form) for the blocks given."""
    output = "Course Number,Schedule Name,Date,Time,Section,Class Length,Student ID, Last Name, First Name,Attendance\n"
    for block in blocks:
        output += scan_breakdown(block, options)
    return output


def is_multi_section_class(cm, sections):
    """
    Are all given sections in this same class (i.e. same course, same time)?
    """
    cms = ClassMeeting.objects.filter(course=cm.course, date=cm.date, time_start=cm.time_start, section__in=sections, room=cm.room)
    classmeeting_count = cms.count()
    return classmeeting_count == len(sections)
       
       
def print_list(options, date):
    """
    Display helpful information for building report block definitions
    """
    if not options.sections:
        classes_today = (c for c in ClassMeeting.objects.filter(date=date, section=SECTIONS[0]) if c.is_all_school() and c.is_first_hour())
    else:
        classes_today = (c for c in ClassMeeting.objects.filter(date=date, section=options.sections[0]) if is_multi_section_class(c, options.sections) and c.is_first_hour())
    classes_today = sorted(list(classes_today), key=operator.attrgetter("time_start"))
    
    print "\nCLASSES:"
    for aclass in classes_today:
        _time = aclass.time_start.strftime("%I%p").strip("0")
        print "[%s] %s, %s, %s hours" % (aclass.course.pk, aclass.course.schedule_name, _time, aclass.number_of_hours())
    print "\nSTAFF SCANS:"
    next_day = date + datetime.timedelta(1)
    scans = Scan.objects.filter(timestamp__gte=date, timestamp__lt=next_day).exclude(person__kind=STUDENT_KIND).order_by("timestamp")
    for scan in scans:
        print "[%s] %s %s" % (scan.person.pk, scan.person, scan.timestamp.time())


def get_classes(options, date):
    """
    Fetch class blocks relevant to provided options
    """
    if not options.sections:
        # We only fetch one section's CMs because we only want one CM for each time slot
        classes_today = ClassMeeting.objects.filter(date=date, section=SECTIONS[0])
        big_meetings = [c for c in classes_today if c.is_first_hour() and c.is_all_school()]
    else:
        classes_today = ClassMeeting.objects.filter(date=date, section=options.sections[0])
        big_meetings = [c for c in classes_today if c.is_first_hour() and not c.is_open() and is_multi_section_class(c, options.sections)]
    blocks = [ClassBlock(cm) for cm in big_meetings]
    return blocks


def marked_blocks(options, date, course):
    """
    Generate block objects for time blocks marked by indicated staffer's scans
    """
    next_day = date + datetime.timedelta(1)
    marker_person = Person.objects.get(pk=int(options.marker))
    scans = Scan.objects.filter(timestamp__gte=date, timestamp__lt=next_day, 
        person=marker_person).order_by("timestamp")
    scan_pairs = [scans[i:i+2] for i in range(0, len(scans), 2)]
    blocks = []
    for meeting_start, meeting_end in scan_pairs:
        # Mildly hacky: We have the time objects, but we make strings
        startspan = "-" + str(meeting_start.timestamp.time())
        endspan = str(meeting_end.timestamp.time()) + "-"
        blocks.append(Block(course, date, startspan, endspan))
    return blocks


if __name__ == "__main__":
    parser = OptionParser("%prog [options] [blocks]")
    parser.add_option("-c", "--classmode",
        action="store_true", help="Look for classes (if classes ran according to schedule)")
    parser.add_option("-t", "--today",
        action="store_true", help="Report is for today")
    parser.add_option("-d", "--date",
        help="Report is for this date")
    parser.add_option("-s", "--sections",
        metavar=SECTIONS, help="Sections to include in report")
    parser.add_option("-l", "--list",
        action="store_true", help="For given date, list courses and staff scans (and their PK numbers)")
    parser.add_option("-k", "--marker",
        help="Staff member PK for scans marking the block start/stop times (use -l to get PK)")
    parser.add_option("-m", "--mail",
        dest="mail_to", 
        help="Email the report to the given address (or multiple addresses separated by commas and no space).")
    parser.add_option("-x", "--test",
        action="store_true", help="Run tests")
    (options, args) = parser.parse_args()

    if options.test:
        doctest.testmod()
        sys.exit()
        
    if options.sections:
        options.sections = options.sections.upper()

    if options.today:
        date = datetime.date.today()
    elif options.date:
        date = datetime.datetime.strptime(options.date, "%Y-%m-%d").date()
    else:
        print "\nERROR: Either --date or --today are required. Use --help for help."
        sys.exit()
        
    if options.list:
        print_list(options, date)
        print "\nBlock format:  311,8:30:00-9:00:07,11:55:30-12:25:30  (course PK, scan-in time, scan-out time)\nOmit either start or end time (leaving the dash) for an automatic %s minute window. Use --help for help." % (scan_window_length.seconds / 60)
        sys.exit()
        
    if options.classmode: 
        blocks = get_classes(options, date)
        sys.exit()
    elif options.marker:
        course = Course.objects.get(pk=int(args[0]))
        blocks = marked_blocks(options, date, course)
    else:  # Block mode
        blocks = []
        for arg in args:
            course_pk, startspan, endspan = arg.split(",")
            course = Course.objects.get(pk=course_pk)
            blocks.append(Block(course, date, startspan, endspan))
        if not blocks:
            print "\nERROR: no blocks provided"
            sys.exit()
    output = report(blocks, options)
    if options.mail_to:
        recipients = options.mail_to.split(",") + [email for name, email in settings.MANAGERS]
        subject = "Scanned attendance report for %s" % date
        send_mail(subject, output, settings.DEFAULT_FROM_EMAIL, recipients)
    else:
        print output
