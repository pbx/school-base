#!/usr/bin/env python
# coding: utf-8

"""
Import students' local address data as recorded via backdrop.hallmark.edu
and exported to a CSV.
"""

import csv
import optparse
import os
os.environ['DJANGO_SETTINGS_MODULE'] = "settings"
from infobase.models import Person, STUDENT_KIND


class AddressRow(object):
    # Update to column list match provided CSV if needed.
    # Names in column list should be Person object field names.
    colnames = ["id_number", "student_address_1", "student_city", 
        "student_state", "student_zip", "primary_phone", "email"]
    colmap = dict(zip(colnames, range(len(colnames))))

    def __init__(self, row):
        self.data = row
        
    def __getattr__(self, column):
        try:
            return self.data[self.colmap[column]]
        except IndexError:
            print "# Bad row: %s" % self.data

    def __str__(self):
        return self.id_number or ",".join(self.data) + " (NO ID)"


def process_csv(path, options):
    reader = csv.reader(open(path, "U"))
    raw_rows = list(reader)
    print "# Read %d rows" % len(raw_rows)
    all_students = Person.objects.filter(kind=STUDENT_KIND)
    updated_students = []
    for raw_row in raw_rows:
        row = AddressRow(raw_row)
        add_address(AddressRow(raw_row), options)
        updated_students += [row.id_number]
    if options.listmissing:
        missing_students = [s for s in all_students if s.id_number not in updated_students and s.is_enrolled()]
        if missing_students:
            print "# No data in CSV for:"
            print "\n".join("%s (%s)" % (str(s), s.id_number) for s in missing_students)
        else:
            print "# All enrolled students found."


def add_address(data, options):
    """
    Find student corresponding to the given row, then save their address data 
    (per options.update).
    """
    try:
        person = Person.objects.get(id_number=data.id_number)
        if options.listfound:
            if (person.student_address_1 or person.student_city or person.student_state or person.student_zip) and not options.forceupdate:
                print "Address data already present for %s; skipping" % person
            else:
                print "Found %s" % person
        else:
            for colname in AddressRow.colnames:
                value = getattr(data, colname)
                setattr(person, colname, value)
            if options.update:
                print "Saving address data for %s" % person
                person.save()
    except Person.DoesNotExist:
        print "# Can't find: %s" % data


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-u", "--update",
        action="store_true",
        help="Perform update (otherwise, just verify data)")
    parser.add_option("-f", "--forceupdate",
        action="store_true",
        help="Force update, even if address data already present")
    parser.add_option("-c", "--csv",
        dest="csvpath", 
        help="CSV data source: ID number, street, city, state, zip")
    parser.add_option("--listmissing",
        action="store_true",
        help="List missing students")
    parser.add_option("--listfound",
        action="store_true",
        help="List found students")
    (options, args) = parser.parse_args()
    options.update = options.forceupdate
    if not options.csvpath or not os.path.exists(options.csvpath):
        parser.print_help()
    else:
        process_csv(options.csvpath, options)
