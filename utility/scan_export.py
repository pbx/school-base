#!/usr/bin/env python
"""
Export scan data for provided date, in CSV form.
"""

import csv
import datetime
import os
import sys
import time
from optparse import OptionParser
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from infoserver.infobase.models import Scan


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-d", "--date",
        dest="date", 
        help="YYYY-MM-DD")
        
    (options, args) = parser.parse_args()

    if not options.date:
        print "Error: '--date' argument is required. Use '-h' option for help."
        sys.exit()

    date = datetime.date(*time.strptime(options.date, "%Y-%m-%d")[:3])

    writer = csv.writer(sys.stdout)
    writer.writerow(["Student ID", "Last Name", "First Name", "Timestamp"])
    rows = Scan.barcode_scans_for_date(date).order_by('timestamp')
    for row in rows:
        row_data = [row.person.id_number, row.person.lastname, row.person.preferred_firstname, row.timestamp]
        writer.writerow(row_data)
