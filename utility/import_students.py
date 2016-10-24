#!/usr/bin/env python
# coding: utf-8

"""
Import new students from CSV. See help text for more detail.
"""

import csv
import optparse
import os
import sys
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from infoserver.infobase.models import Person
from infoserver.infobase.models import PHASE_END_DATES


def read_data(options):
    """
    Ingest data from file; return rows.
    """
    reader = csv.reader(open(options.datafile, "U"))
    raw_rows = list(reader)
    fieldnames = raw_rows[0]
    rows = []
    for raw_row in raw_rows[1:]:
        row = {}
        try:
            for i in range(len(fieldnames)):
                row[fieldnames[i]] = raw_row[i]
            rows.append(row)
        except IndexError:
            print "SHORT ROW:", raw_row
    print "Read %d rows" % len(rows)
    return rows
    

def process_data(rows, options):
    """
    Take a list of rows and create a new student for each.
    """
    cohort = int(options.cohort)
    id_expiry = PHASE_END_DATES[cohort][4]
    for row in rows:
        new_student = Person()
        for k, v in row.items():
            setattr(new_student, k, v)
            new_student.student_cohort = cohort
            new_student.id_expiry = id_expiry
            if options.section:
                new_student.student_sec_phase1 = options.section
        if options.add:
            new_student.save()
            print "Saved:", new_student


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-a", "--add",
        action="store_true",
        help="Add the students (otherwise, just verify data)")
    parser.add_option("-d", "--datafile",
        help="CSV file with student data (field names in first row)")
    parser.add_option("-c", "--cohort",
        help="Cohort number. Required. (1=September, 2=January)")
    parser.add_option("-s", "--section",
        help="Section letter (optional)")
    (options, args) = parser.parse_args()
    if options.datafile:
        rows = read_data(options)
        process_data(rows, options)
    else:
        print "Need a data file"
    if not options.cohort:
        print "Need a cohort"
        
## TODO: set id expiry. don't add if no lastname present.