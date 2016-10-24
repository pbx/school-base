#!/usr/bin/env python
import csv
import datetime
from optparse import OptionParser
import os
import sys
import time
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from infoserver.infobase.models import Person

class DobRow(object):
    """Abstraction to make handling CSVs a little cleaner"""
    colnames = "id_number date".split()
    colmap = dict(zip(colnames, range(len(colnames))))

    def __init__(self, row):
        self.data = row
        
    def __getattr__(self, column):
        """Return value from the named column -- with special logic for dates."""
        datum = self.data[self.colmap[column]]
        if column == "date":
            year, month, day = list(time.strptime(datum, "%m/%d/%Y")[0:3])
            # strptime will add 100 to years that predate the Unix epoch.
            # So we check for years that seem to have resulted from that.
            latest_reasonable_year = datetime.date.today().year - 15
            if year > latest_reasonable_year:
                year -= 100
            return datetime.date(year, month, day)
        else:
            return datum

    def __str__(self):
        return str(self.data)


def read_csv(path, dialect="excel", update=False):
    reader = csv.reader(open(path, 'U'), dialect=dialect)
    rows = list(reader)  #  We assume first row isn't labels
    print 'Read %d Rows' % len(rows)
    for raw_row in rows:
        read_dob(raw_row, update=update)
            

def read_dob(raw_row, update=False):
    """Read a row from CSV file and update object in db"""
    row = DobRow(raw_row)
    try:
        person = Person.objects.get(id_number=str(row.id_number))
        birthdate = row.date
    except Person.DoesNotExist:
        raise KeyError, "Person not found for id %s" % row.id_number
    except ValueError:
        raise ValueError, "BAD DATE for %s (%s)" % (row.id_number, person)
    if update:
        print person, birthdate
        person.date_of_birth = birthdate
        person.save()
        

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-u", "--update",
        dest="update_data",
        action="store_true",
        help="Perform update (otherwise, just verify data)")
    parser.add_option("-c", "--csv",
        dest="csvpath", 
        help="CSV file (ID number, birthdate) to import from")
    (options, args) = parser.parse_args()
    if not options.csvpath or not os.path.exists(options.csvpath):
        print "CSV FILE NOT FOUND!"
        parser.print_help()
        sys.exit()
    else:
        read_csv(options.csvpath, update=options.update_data)
