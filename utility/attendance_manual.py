#!/usr/bin/env python
"""
Attendance reporting script for classes (versus all-school events)
"""

import sys
import os
import datetime
import time
from optparse import OptionParser, OptParseError
os.environ['DJANGO_SETTINGS_MODULE'] = "settings"
from django.core.mail import send_mail
from django.conf import settings
from infobase.models import Scan, Person, ClassMeeting, SECTIONS


def classmeeting_report_markdown(c):
    output = "\n%s\n### %s\n" % ("-"*80, c.report_header())
    if c.instructors.count():
        output += "#### Instructors: %s\n" % c.instructor_list()
    output += "\n"
    present, absent = c.attendance()
    if present:
        output += "**PRESENT (%s)**" % len(present) + "\n"
        output += ", ".join(unicode(p) for p in present) + "\n\n"
    if absent:
        output += "**ABSENT (%s)**" % len(absent) + "\n"
        output += ", ".join(unicode(a) for a in absent) + "\n\n"
    return output


def classmeeting_report_csv(c):
    output = ""
    expected = Person.objects.section(c.section, c.date, inclusive=True)
    present_raw = sorted(s.person for s in c.scan_set.all())
    classinfo = '"%s","%s","%s",%s,%s,%s' % (c.course.course_number, c.course.schedule_name, c.date, "%d:%02d" % (c.time_start.hour, c.time_start.minute), c.section, c.number_of_hours())
    for student in expected:
        output += '%s,"%s","%s","%s",' % (classinfo, student.id_number, student.lastname, student.firstname)
        if student in present_raw:
            output += "present"
        else:
            output += "absent"
        output += "\n"
    return output


def scanned_attendance_class(cm):
    """
    Is this class (likely) a class where attendance was taken by scanning?
    Our heuristic: if it's more than 5 sections at once and not an open class, yes.
    (Open classes are included in the report because they're needed for Matt's stage of the reporting process.)
    """
    cms = ClassMeeting.objects.filter(course=cm.course, date=cm.date, time_start=cm.time_start, room=cm.room)
    return cms.count() > 5 and not cm.is_open()


def prep_classmeeting_list(classes):
    """
    Prepare ClassMeeting list for report: sort, and remove scanned-attendance classes
    """
    def course_cmp(c1, c2):
        if c1.course == c2.course:
            if c1.section == c2.section:
                return cmp(c1.time_start, c2.time_start)
            else:
                return cmp(SECTIONS.index(c1.section), SECTIONS.index(c2.section))
        else:
            return cmp(str(c1.course), str(c2.course))
            
    class_list = [c for c in classes if c.is_first_hour() and not scanned_attendance_class(c)]
    return sorted(class_list, cmp=course_cmp)


if __name__ == "__main__":
    parser = OptionParser(usage="Generate attendance report.")
    parser.add_option("-c", "--csv",
        dest="csv_flag",
        action="store_true", 
        help="CSV output format")
    parser.add_option("-k", "--markdown",
        dest="markdown_flag",
        action="store_true", 
        help="Markdown output format")
    parser.add_option("-d", "--date",
        dest="report_day",
        help="Single-day report")
    parser.add_option("-t", "--today",
        dest="today_only", 
        action="store_true",
        help="Single-day report for today")
    parser.add_option("-w", "--week",
        dest="week_start",
        help="Week report")
    parser.add_option("-m", "--mail",
        dest="mail_to", 
        help="Email the report to the given address (or multiple addresses separated by commas and no space).")

    (options, args) = parser.parse_args()
    classes = None
    try:         
        if options.today_only:
            report_day = datetime.date.today() 
            classes = ClassMeeting.objects.filter(date=report_day)
            header = "Manual Attendance Report for %s" % report_day
        if options.report_day:
            report_day = datetime.datetime.strptime(options.report_day, "%Y-%m-%d")
            classes = ClassMeeting.objects.filter(date=report_day)
            header = "Manual Attendance Report for %s" % report_day
        elif options.week_start:
            week_start = datetime.datetime.strptime(options.week_start, "%Y-%m-%d")
            week_end = week_start + datetime.timedelta(5)
            classes = ClassMeeting.objects.filter(date__gte=week_start, date__lte=week_end)
            header = "Manual Attendance Report for week of %s" % week_start.strftime("%Y-%m-%d") 
    except (ValueError):
        pass
        
    if not classes:
        parser.print_help()        
        sys.exit()

    if options.csv_flag:
        output = "Course Number,Schedule Name,Date,Time,Section,Class Length,Student ID,Last Name,First Name,Attendance\n"
    elif options.markdown_flag:
        output = "# %s\n" % header
    else:
        print "Must specify either --csv or --markdown output format"
        sys.exit()
        
    classes = prep_classmeeting_list(classes)
    for c in classes:
        if options.csv_flag:
            output += classmeeting_report_csv(c).encode("latin-1")
        elif options.markdown_flag:
            output += classmeeting_report_markdown(c).encode("latin-1")
    if options.mail_to:
        recipients = options.mail_to.split(",") + [email for name, email in settings.MANAGERS]
        send_mail(header, output, settings.DEFAULT_FROM_EMAIL, recipients)
    else:
        print output
