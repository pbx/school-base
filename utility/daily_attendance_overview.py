#!/usr/bin/env python
"""
Attendance overview report

This generates a text file which summarizes the day's attendance
to identify classes where all students are absent (indicating
that the instructor may have forgotten to submit attendance).

The output of this script is valid Markdown, in case that's useful.
"""

import os
import datetime
from optparse import OptionParser
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from django.core.mail import send_mail
from django.conf import settings
from infoserver.infobase.models import ClassMeeting


def classmeeting_summary(classmeeting):
    vitals = "%s (%s) %s" % (classmeeting.course, classmeeting.section, classmeeting.time_start)
    present, absent = classmeeting.attendance()
    if present:
        output = "%s/%s -- %s" % (len(present), len(absent), vitals)
    elif classmeeting.is_all_school():
        output = "ALL SCHOOL -- %s" % vitals
    else:
        output = "NONE PRESENT -- %s -- %s" % (vitals, classmeeting.instructors.all()[0]) 
    return output


def meeting_cmp(c1, c2):
    """Comparison function to aid in sorting a list of classmeetings."""
    if c1.course == c2.course:
        return cmp(c1.datetime_start(), c2.datetime_start())
    else: 
        return cmp(str(c1.course), str(c2.course))


def summarize(classmeetings):
    """
    Produce an attendance summary, one line per classmeeting.
    Headers for each day are ready for multi-day reports.
    """
    classmeetings = sorted(classmeetings, cmp=meeting_cmp)
    output = "# Attendance Summary\n\n"
    working_date = None
    class_count = 0
    for meeting in classmeetings:
        if meeting.date != working_date:
            output += "## %s\n\n" % meeting.date
            working_date = meeting.date
        if not meeting.is_open() and meeting.has_started() and meeting.is_first_hour():
            output += classmeeting_summary(meeting) + "  \n"
            class_count += 1
    if class_count:
        return output

    
if __name__ == '__main__':
    today = datetime.date.today()
    parser = OptionParser()
    parser.add_option("-m", "--mail",
        dest="mail_to", 
        help="Email the report to the given address (or multiple addresses separated by commas and no space).")
    parser.add_option("-d", "--date",
        dest="date", 
        help="Show report from a specific date.")

    (options, args) = parser.parse_args()

    report_day = options.date or today
    classes = ClassMeeting.objects.filter(date=report_day)
    if classes.count():
        output = summarize(classes)
        if output:
            if options.mail_to:
                recipients = options.mail_to.split(",") + [email for name, email in settings.MANAGERS]
                subject = "Attendance summary for %s" % report_day
                send_mail(subject, output, settings.DEFAULT_FROM_EMAIL, recipients)
            else:
                print output
