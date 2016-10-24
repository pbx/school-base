#!/usr/bin/env python
# coding: utf-8

"""
Import equipment serial numbers from text files. See help text for more detail.
"""

import csv
import optparse
import os
import sys
os.environ['DJANGO_SETTINGS_MODULE'] = "infoserver.settings"
from django.db.models import Q
from infoserver.equipment.models import Item, ItemType


def read_data(options):
    """
    Ingest data from file, adding to database if options so instruct.
    """
    # We read the file with csv.reader regardless of options.csv setting, because
    # a plain list of numbers can be treated as a one-column csv
    reader = csv.reader(open(options.datafile, "U"))
    rows = list(reader)
    numbers = [row[options.column] for row in rows]
    print "Read %d numbers" % len(rows)
    return numbers
    

def check_data(number_list, options):
    """Perform basic checks on provided numbers, and halt if problems are found."""
    trouble = False
    std_num_len = len(number_list[0])
    for number in number_list:
        dupes = Item.objects.filter(Q(hip_number=number)|Q(serialnumber=number)).count()
        if dupes:
            print "Number %s already present: %s" % (number, Item.find_by_number(number))
            trouble = True
        if len(number) != std_num_len:
            print "Number %s is different length (%s instead of %s)" % (number, len(number), std_num_len)
            trouble = True
    if trouble:
        sys.exit()


def process_data(number_list, options):
    """
    Take a list of numbers and create a new equipment item for each. ItemType is specified in options.itemtype.
    """
    check_data(number_list, options)
    added_count = 0
    for number in number_list:
        number = number.upper()  # Normalize to upper case
        if options.hipnumber:
            new_item = Item(itemtype=options.itemtype, hip_number=number)
        else:
            new_item = Item(itemtype=options.itemtype, serialnumber=number)
        if options.add:
            new_item.log_this("Added from %s" % options.datafile)
            new_item.save()
            added_count += 1
    print "Added %s new items (%s)" % (added_count, options.itemtype)


if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-a", "--add",
        action="store_true",
        help="Add the items (otherwise, just verify data)")
    parser.add_option("-c", "--column",
        help="Data file is CSV, with serial numbers in specified column (otherwise, data file has one number per line or is a CSV with numbers in first column).")
    parser.add_option("-d", "--datafile")
    parser.add_option("-i", "--itemtype",
        help="Type of item, by number (use -s option to see numbers).")
    parser.add_option("-n", "--hipnumber",
        action="store_true",
        help="Store numbers in HIP-number field, not serial-number field.")
    parser.add_option("-s", "--showtypes",
        action="store_true",
        help="List available item types.")
    (options, args) = parser.parse_args()
    if options.itemtype:
        try:
            options.itemtype = ItemType.objects.get(id=options.itemtype)
            print "Item type: %s" % options.itemtype
        except ItemType.DoesNotExist:
            print "Unknown item ID: %s" % options.itemtype
            parser.print_help()
    if not options.column:
        options.column = 0   # first-column default or plain list of numbers
    if options.showtypes:
        for itemtype in ItemType.objects.all():
            print "%s: %s" % (itemtype.id, itemtype)
    if options.datafile:
        number_list = read_data(options)
        process_data(number_list, options)
    if not options.itemtype or options.showtypes:
        parser.print_help()
