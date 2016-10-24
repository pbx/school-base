#!/usr/bin/env python
"""
Utility script for generating arbitrary CSV files

TODO: safely escape newlines; add (optional) column headers
"""

import sys
import csv
import MySQLdb
from optparse import OptionParser

if __name__ == '__main__':
    parser = OptionParser(usage="To generate CSV output from a MySQL table:\n%prog [ --table TABLENAME | --list-tables ] column1 column2 ...")
    parser.add_option("-w", "--where",
        dest="where", 
        help="SQL WHERE clause (quoted)")
    parser.add_option("-u", "--user",
        default="root",
        dest="user", 
        help="database user")
    parser.add_option("-d", "--db",
        default="infoserver",
        dest="db", 
        help="database name")
    parser.add_option("-p", "--passwd",
        default = "",
        dest="passwd", 
        help="database user's password")
    parser.add_option("-o", "--host",
        default="localhost",
        dest="host", 
        help="database host")
    parser.add_option("-t", "--table",
        dest="table", 
        help="table name")
    parser.add_option("-l", "--list-tables",
        action="store_true",
        dest="list", 
        help="list all tables")
    parser.add_option("-s", "--schema",
        action="store_true",
        dest="show_schema", 
        help="show table definition")
        
    (options, args) = parser.parse_args()

    if len(args) == 0:
        cols = "*"
    else:
        cols = ",".join(args)
    where = ""
    if options.where:
        where = "WHERE " + options.where

    if options.list:
        query = "SHOW TABLES"
    elif not options.table:
        print "Error: '--table' argument or '--list-tables' is required. Use '-h' option for help."
        sys.exit()
    elif options.show_schema:
        query = "SHOW CREATE TABLE %s" % options.table
    else:
        query = "SELECT %s from %s %s" % (cols, options.table, where)

    conn = MySQLdb.connect(user=options.user, db=options.db, passwd=options.passwd, host=options.host)
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    writer = csv.writer(sys.stdout)   
    for row in rows:
        writer.writerow(row)
    print  # ssmtp drops the last line fed to it if there's no newline
