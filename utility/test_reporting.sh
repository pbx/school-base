#!/bin/bash
/Library/Django/projects/infoserver/utility/attendance_scanned.py -d 2010-03-11 -stripod 287,-8:01:57,11:31:36- | diff -u - ~master/data/attendance_reports_out/_test_report_1.csv 
/Library/Django/projects/infoserver/utility/attendance_by_class.py -d 2010-03-11 -c | diff -u - ~master/data/attendance_reports_out/_test_report_2.csv 
