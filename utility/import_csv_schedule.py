#!/usr/bin/env python
"""
Import schedule data from CSV files (prepared from weekly schedule Excel files)
into the infoserver attandance database. Performs some data integrity checks.
"""
import csv
import datetime
import os
import sys
import time
from optparse import OptionParser
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from infoserver.infobase.models import Course, Room, ClassMeeting, Person

FACULTY_KIND = Person.PEOPLE_TYPES_MAPPING["Faculty"]

def abort(message="ABORTING IMPORT. Check your CSV data."):
    """General purpose bail-out function"""
    print message
    sys.exit()

class ScheduleRow(object):
    """Abstraction to make handling class-schedule CSVs a little cleaner"""
    colnames = "date week time_start time_end section schedule_name course_number instructors hours location".split()
    colmap = dict(zip(colnames, range(len(colnames))))
    def __init__(self, row):
        if len(row) != len(self.colmap):
            message = "ROW LENGTH INCORRECT: %s columns expected, %s found\n%s" % (len(self.colmap), len(row), row) 
            raise ValueError, message
        self.data = row
    def __getattr__(self, key):
        value = self.data[self.colmap[key]]
        if value.upper() == "GUEST" and key == "instructors":
            value = "Q"
        return value
    def __str__(self):
        return str(self.data)

def import_csv(csvpath, import_data=False):
    """
    Import schedule data from CSV file
    """
    if not import_data:
        print "TEST MODE (not importing data)"
    csvfile = open(csvpath, 'U')
    reader = csv.reader(csvfile)
    rows = list(reader)
    # Strip out headers if they're present
    csvfile.seek(0)
    if csv.Sniffer().has_header(csvfile.read()):
        print "Dropping header row"
        rows = rows[1:]
    csvfile.close()
    # Perform the import
    print 'Read %d rows' % len(rows)
    for raw_row in rows:
        import_class(raw_row, import_data)
    if not import_data:
        print "TEST COMPLETE"

def import_class(raw_row, import_data=False):
    """
    Read a row from login CSV file and create objects in db
    """
    try:
        row = ScheduleRow(raw_row)
    except ValueError, message:
        print message
        if import_data:
            abort(message)
        else:
            return
    row.course_number = row.course_number[:10]  # Field length limit
    try:
        course = Course.objects.get(course_number=row.course_number, schedule_name=row.schedule_name)
    except Course.DoesNotExist:
        course = Course(course_number=row.course_number, schedule_name=row.schedule_name)
        print "%s %s %s: %s (%s)" % (row.course_number, row.date, row.time_start, row.schedule_name, row.instructors)
        if import_data:
            course.save()
    try:
        room = Room.objects.get(abbreviation=row.location)
    except Room.DoesNotExist:
        room = Room(abbreviation=row.location)
        if import_data:
            room.save()

    cleaned_instructor_list = ''.join(i.upper() for i in row.instructors if i.isalpha())  
    try:
        instructors = Person.objects.instructors(cleaned_instructor_list)
    except Person.DoesNotExist:
        print "Unknown instructor in '%s'" % cleaned_instructor_list

    
    date = datetime.datetime.strptime(row.date, "%m/%d/%y")
    time_start = datetime.datetime.strptime(row.time_start, "%H:%M")

    try:
        class_meeting = ClassMeeting.objects.get(course=course, date=date, time_start=time_start, room=room, section=row.section)
        print "CLASS ALREADY IMPORTED:", class_meeting
        if import_data:
            abort()
    except ClassMeeting.DoesNotExist:
        class_meeting = ClassMeeting(course=course, date=date, time_start=time_start, room=room, section=row.section)
        if import_data:
            class_meeting.save()  # Need to save before we attach instructors
            for instructor in instructors:
                class_meeting.instructors.add(instructor)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-i", "--import",
        dest="import_data",
        action="store_true",
        help="Perform import (otherwise, just verify data)")
    parser.add_option("-c", "--csv",
        dest="csvpath", 
        help="Schedule CSV file to import from")
    (options, args) = parser.parse_args()
    if not options.csvpath or not os.path.exists(options.csvpath):
        print "CSV FILE NOT FOUND!"
        parser.print_help()
        sys.exit()
    import_csv(options.csvpath, import_data=options.import_data)
