#!/usr/bin/env python
import csv
import datetime
import optparse
import os
import sys
import time
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from infoserver.infobase.models import Vehicle, Person

class VehicleRow(object):
    """Abstraction to make handling CSVs a little cleaner"""
    colnames = "make model year color plate_number plate_state permit_number id_number".split()
    colmap = dict(zip(colnames, range(len(colnames))))

    def __init__(self, row):
        self.data = row
    def __getattr__(self, key):
        return self.data[self.colmap[key]]
    def __str__(self):
        return str(self.data)

def import_csv(options):
    reader = csv.reader(open(options.csv, "U"), dialect=options.dialect)
    rows = list(reader)
    print "Read %d vehicles" % len(rows)
    for raw_row in rows:
        add_vehicle(raw_row, options)

def add_vehicle(raw_row, options):
    """Read a row from CSV file and create object in db"""
    row = VehicleRow(raw_row)
    try:
        person = Person.objects.get(id_number=str(row.id_number))
    except Person.DoesNotExist:
        raise KeyError, "Person not found for id %s" % row.id_number
    try:
        dupe = Vehicle.objects.get(plate_number=row.plate_number, plate_state=row.plate_state)
        print "Vehicle exists: %s" % dupe
    except Vehicle.DoesNotExist:
        atts = { 'owner': person }
        for col, default in [("year", 0), ("make", "Unknown"), ("model", "Unknown")]:
            if not getattr(row, col):
                setattr(row, col, default)
        for att in set(row.colnames) - set(["id_number"]):
            atts[att] = getattr(row, att)
        vehicle = Vehicle(**atts)
        print person, vehicle
        if not options.test:
            vehicle.save()


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-c", "--csv", help="Path to CSV file")
    parser.add_option("-d", "--dialect", default="excel", help="CSV dialect (default: excel)")
    parser.add_option("-t", "--test", action="store_true", help="Test mode (don't save)")
    (options, args) = parser.parse_args()
    
    if options.csv:
        import_csv(options)
    else:
        print "Need a CSV file."
