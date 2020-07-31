# school-base

Built for a photography/business school that is no longer in operation, this system managed student information, class schedules and attendance-taking, and equipment loan. It also was used to generate printed material like manual attendance lists and student face-sheets. It replaced and superseded several FileMaker databases, a proprietary MS Access app, many Excel spreadsheets, and lots of paper.

![attendance scan screen](http://paulbissex.com/img/hallmark-scan.png)

Large-group classes had attendance kiosks where students would scan their ID barcodes to sign in; these kiosks' web browsers were set to load the `/scan/` page and had USB barcode readers that entered the scanned ID numbers and send a carriage return to submit the form.

For smaller classes, instructors took attendance manually on-screen, or via their phones.

The school had a lending library of photography equipment, which was managed through this system as well, including grouping equipment into "kits", assessing late-return penalties, and so on. 

To understand the code, read the doctests. I haven't worked on it in many years, I found them informative myself!

_Note: This is a legacy system that was actively developed from 2006 to 2010. Released as open source in 2016. Porting to modern Django shouldn't be too laborious, but if you want to try it out as-is, expect some rough edges. Uses [Django 0.97](https://github.com/django/django/tree/babfe78494028415b0e5f74ec2ca9b66506e8d34) &mdash; retro!_
