"""
Equipment tracker. 

This app is used for daily check-in/check-out operations in the equipment
room ("cage") as well as tracking year-long signout of gear to students and faculty.

Examples and tests:


# Every item has an ItemType. Here are a couple common ones.
>>> camera = ItemType.objects.create(manufacturer="Canon", modelname="5D Mark II")
>>> lens = ItemType.objects.create(manufacturer="Canon", modelname="24-70mm")

# Adding inventory
>>> Item.objects.create(itemtype=camera, serialnumber="2345")
<Item: Canon 5D Mark II #2345>
>>> Item.objects.create(itemtype=camera, serialnumber="4567")
<Item: Canon 5D Mark II #4567>
>>> Item.objects.create(itemtype=lens, serialnumber="8765")
<Item: Canon 24-70mm #8765>
>>> print camera.how_many_in_stock()  # Newly created items are INSTOCK by default
2
>>> print lens.how_many_in_stock()
1

# HIP number and serial number together must be unique.
# The .find_by_number method looks up by HIP number, then by serial number
>>> Item.objects.create(itemtype=camera, serialnumber="4567")
Traceback (most recent call last):
...
IntegrityError: (1062, "Duplicate entry '4567-' for key 2")
>>> Item.objects.create(itemtype=camera, hip_number="C1", serialnumber="4567")
<Item: Canon 5D Mark II #C1>
>>> Item.find_by_number("4567")  # Fails because it's not unique
Traceback (most recent call last):
...
ItemError
>>> Item.find_by_number("C1")
<Item: Canon 5D Mark II #C1>
>>> print Item.find_by_number("C1").number
C1
>>> print Item.find_by_number("2345").number
2345

# Fetch some items and give them names for our tests
>>> a_5d = Item.find_by_number("2345")
>>> print a_5d
Canon 5D Mark II #2345
>>> a_lens = Item.find_by_number("8765")
>>> print a_lens
Canon 24-70mm #8765

# Transactions
# At a few critical points in tests we pause to avoiding race conditions
>>> norace = lambda: time.sleep(1)  
>>> norace()
>>> bob_dobbs = Person.objects.create(firstname="Bob", lastname="Dobbs", id_number="1974001")
>>> a_5d.check_out(bob_dobbs) ; a_5d.save()
>>> a_5d.transaction_set.all()
[<Transaction: Canon 5D Mark II #2345 checked out by Bob Dobbs (...)>]
>>> a_5d.is_checked_out
True
>>> a_5d.due >= datetime.datetime.now() + datetime.timedelta(days=1)
True
>>> a_5d.set_due_datetime(datetime.datetime(1974, 1, 1))  # Set custom due date
>>> bool(a_5d.days_overdue())
True
>>> a_5d.set_due_datetime()  # Set due date back to default
>>> a_5d.days_overdue()
0
>>> one_minute_late = a_5d.due + datetime.timedelta(minutes=1)
>>> a_5d.days_overdue(as_of=one_minute_late)
1
>>> one_minute_and_one_day_late = a_5d.due + datetime.timedelta(days=1, minutes=1)
>>> a_5d.days_overdue(as_of=one_minute_and_one_day_late)
2
>>> a_5d.days_overdue(as_of=datetime.datetime(1974,01,01))
0
>>> bool(a_5d.days_overdue(as_of=datetime.datetime(2074,01,01)))
True
>>> print camera.how_many_out()
1
>>> print a_5d.checked_out_by
Bob Dobbs
>>> print bob_dobbs.item_set.all()
[<Item: Canon 5D Mark II #2345>]
>>> norace()
>>> a_5d.check_in()
>>> a_5d.save()
>>> a_5d.is_in_stock
True
>>> print camera.how_many_out()
0
>>> print a_5d.checked_out_by
None

# Late penalties
>>> norace()
>>> a_5d.check_out(bob_dobbs)
>>> a_5d.save()
>>> print Penalty.levy(bob_dobbs)  # No penalty; not late yet
None
>>> a_5d.set_due_datetime(a_5d.due - datetime.timedelta(days=10)); a_5d.save()  # Wicked late
>>> penalty = Penalty.levy(bob_dobbs)  # We know he's got late equipment, so penalize him
>>> penalty.amount > 0
True
>>> norace(); a_5d.check_in(); a_5d.save()


# Kits
>>> camerakit = ItemType.objects.create(kit=True, manufacturer="Hallmark", modelname="5D Kit")
>>> print camerakit
Hallmark 5D Kit
>>> a_kit = Item.objects.create(itemtype=camerakit, serialnumber="1974")
>>> a_kit.contents.all()
[]
>>> a_kit.contents.add(a_5d)
>>> a_kit.contents.add(a_lens)
>>> print a_kit.contents.all()
[<Item: Canon 5D Mark II #2345>, <Item: Canon 24-70mm #8765>]
>>> norace()
>>> a_kit.check_out(bob_dobbs)
>>> print a_kit.transaction_set.all()
[<Transaction: Hallmark 5D Kit #1974 checked out by Bob Dobbs (...)>]
>>> a_kit.is_checked_out
True
>>> print a_kit.checked_out_by
Bob Dobbs
>>> due_later = a_kit.due + datetime.timedelta(days=365)
>>> a_kit.set_due_datetime(due_later)
>>> a_kit.save()  # Saving a kit updates the due dates of its items
>>> a_kit.contents.all()[0].due == due_later
True

# A little utility function for re-fetching items that have been updated
>>> refetch = lambda x: x.__class__.objects.get(id=x.id)
>>> a_5d, a_lens = refetch(a_5d), refetch(a_lens)

# Inspect the items' transaction history and their current status -- should match the kit
>>> print [t.get_kind_display()  for t in a_5d.transaction_set.all()]
[u'checked out', u'checked in', u'checked out', u'checked in', u'checked out']
>>> print [t.get_kind_display() for t in a_lens.transaction_set.all()]
[u'checked out']
>>> a_5d.is_checked_out
True
>>> print a_lens.is_checked_out
True
>>> print a_5d.checked_out_by
Bob Dobbs
>>> print a_lens.checked_out_by
Bob Dobbs

# Check it all back in and go home!
>>> a_kit.check_in() ; a_kit.save() ; a_5d, a_lens = refetch(a_5d), refetch(a_lens)
>>> a_kit.is_in_stock
True
>>> print a_kit.checked_out_by
None
>>> a_5d.is_in_stock
True
>>> a_lens.is_in_stock
True
"""

import datetime
import time
from django.db import models
from django.db.models import Q
from infobase.models import Person, STUDENT_KIND


class ItemType(models.Model):
    """
    A type of equipment that we lend out. This model stores information that
    applies to all of the items of the type that we have.
    """
    manufacturer = models.CharField(max_length=100, blank=True, help_text="Canon, Mamiya, etc. For kits: Hallmark")
    modelname = models.CharField(max_length=100, blank=True, help_text="5D Mark II, 645 AFDII, Light Kit, etc.")
    kit = models.BooleanField(default=False)
    note = models.CharField(blank=True, max_length=250)

    class Admin:
        list_filter = ["kit", "manufacturer"]
        list_display = ["__unicode__", "kit", "how_many_in_stock", "how_many_out"]

    class Meta:
        ordering = ["manufacturer", "modelname"]
        
    def __unicode__(self):
        return u"%s %s" % (self.manufacturer, self.modelname)
        
    def how_many_in_stock(self):
        """How many of this item are in stock right now?"""
        return self.item_set.filter(status=Item.INSTOCK).count()

    def how_many_out(self):
        """How many of this item are checked out right now?"""
        return self.item_set.filter(status=Item.OUT).count()


class ItemError(Exception):
    def __init__(self, message=None):
        self.message = message
    def __unicode__(self):
        return self.message


class Item(models.Model):
    """
    An individual piece of equipment that is lent out.
    """
    INSTOCK, OUT, REPAIR = 1, 2, 3
    STATUS_CHOICES = [(INSTOCK, "in stock"), (OUT, "checked out"), (REPAIR, "out for repair")]

    itemtype = models.ForeignKey(ItemType)
    serialnumber = models.CharField(blank=True, max_length=100, help_text="Manufacturer's number")
    hip_number = models.CharField(blank=True, max_length=100, help_text="Hallmark-specific number")
    status = models.IntegerField(blank=True, null=True, choices=STATUS_CHOICES, default=INSTOCK)
    checked_out_by = models.ForeignKey(Person, blank=True, null=True, 
        help_text="Person who has this item. (Don't change this via admin area)")
    due = models.DateTimeField(blank=True, null=True)
    part_of_kit = models.ForeignKey("self", blank=True, null=True, related_name="contents",
        limit_choices_to={'itemtype__kit':True},
        help_text="Kit that this item belongs to (if any)")
    log = models.TextField(blank=True)
    note = models.CharField(blank=True, max_length=250)
    
    class Admin:
        list_display = ["__unicode__", "status", "checked_out_by", "due", "is_kit", "part_of_kit", "serialnumber", "hip_number"]
        list_filter = ["status", "itemtype", "due"]
        search_fields = ["note", "log"]
        save_on_top = True

    class Meta:
        ordering = ["itemtype", "hip_number", "serialnumber"]
        unique_together = [("serialnumber", "hip_number")]
        
    def __unicode__(self):
        return u"%s #%s" % (self.itemtype, self.number)

    def save(self):
        """
        Some custom handling of serial numbers and due dates is needed when saving
        """
        if not (self.serialnumber or self.hip_number):
            raise ItemError("Each item needs either a serial number or a HIP number")
        if self.is_kit:  # A kit's contents should be due when the kit is
            for item in self.contents.all():
                item.set_due_datetime(custom_due_datetime=self.due)
                item.save()
        super(Item, self).save()

    def set_due_datetime(self, custom_due_datetime=None):
        """
        Here we set the due-datetime for the item. Monday-Thursday checkouts
        are due the next day at 5:50pm. Friday checkouts are due Monday at 7:50am.
        A custom due-date may be passed.
        """
        if custom_due_datetime:
            self.due = custom_due_datetime
        else:
            today = datetime.date.today()
            if today.isoweekday() == 5:
                due_day = today + datetime.timedelta(days=3)
                due_time = datetime.time(7, 50)
            else:
                due_day = today + datetime.timedelta(days=1)
                due_time = datetime.time(17, 50)
            self.due = datetime.datetime.combine(due_day, due_time)

    @property
    def number(self):
        """Identifying number for this item: hip_number if any, otherwise serialnumber"""
        return self.hip_number or self.serialnumber

    def is_kit(self):
        return self.itemtype.kit
    is_kit.boolean = True
    is_kit = property(is_kit)  # @-style decorator doesn't work with .boolean attr set

    def add_to_stock(self, note=None):
        """Add this item to the inventory."""
        if self.status != self.INSTOCK:
            Transaction.objects.create(item=self, kind=Transaction.ADD, note=note)
            self.status = self.INSTOCK
        if self.is_kit:  # For kits, add all items inside
            for item in self.contents.all():
                item.add_to_stock(note="Added as part of kit %s" % self)
                item.save()

    def check_out(self, person, custom_due_datetime=None, note=None):
        """Check out this item."""
        if self.status != self.INSTOCK:
            raise TransactionError("Item isn't in stock -- %s" % self.get_status_display())
        Transaction.objects.create(item=self, person=person, kind=Transaction.CHECKOUT, note=note)
        self.status = self.OUT
        self.checked_out_by = person
        self.set_due_datetime(custom_due_datetime)
        self.save()
        if self.is_kit:  # For kits, check out all items inside
            for item in self.contents.all():
                item.check_out(person, note="Checked out as part of kit %s" % self)

    def check_in(self, note=None):
        """Check this item back in."""
        if self.status != self.OUT:
            raise TransactionError("Item isn't checked out -- %s" % self.status)
        person = self.checked_out_by
        # Could log late returns by setting note = "LATE" if datetime.datetime.now() > self.due
        Transaction.objects.create(item=self, person=person, kind=Transaction.CHECKIN, note=note)
        self.status = self.INSTOCK
        self.checked_out_by = None
        self.save()
        if self.is_kit:  # For kits, check in all items inside
            for item in self.contents.all():
                item.check_in(note="Checked in as part of kit %s" % self)

    def log_this(self, text):
        """Add a line to the item's log"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log += "[%s] %s\n" % (timestamp, text)
    
    @property
    def is_in_stock(self):
        """Is it in stock?"""
        return self.status == self.INSTOCK
        
    @property
    def is_checked_out(self):
        """Is it checked out?"""
        return self.status == self.OUT

    def days_overdue(self, as_of=None):
        """
        How many days overdue is the item? Where 1 minute late is 1 day, 24:01 late
        is 2 days, etc. If a timestamp is passed, return how many days it would be 
        overdue as of that time.
        """
        if not as_of:
            as_of = datetime.datetime.now()
        if not self.is_checked_out or self.due >= as_of:
            return 0
        how_late = (as_of - self.due).days + 1
        return how_late
        
    @classmethod
    def find_by_number(cls, number):
        """
        Find an item by a scanned number, which may be its HIP number or its serial number
        """
        matches = cls.objects.filter(Q(hip_number=number)|Q(serialnumber=number))
        if matches.count() > 1:
            raise ItemError("Multiple matches for %s: %s" % (number, [item.id for item in matches]))
        elif matches.count() == 0:
            raise ItemError("No item found with serial/HIP number %s" % number)
        else:
            return matches[0]

    def admin_url(self):
        return "/admin/equipment/item/%s/" % self.id


class TransactionError(Exception):
    def __init__(self, message=None):
        self.message = message
    def __unicode__(self):
        return self.message


class Transaction(models.Model):
    """
    A record of action taken with a piece of equipment, especially check in/out.
    """
    ADD, CHECKOUT, CHECKIN, REPAIR_OUT, REPAIR_BACK = 1, 2, 3, 4, 5
    TRANSACTION_KINDS = [(ADD, "added to system"), 
        (CHECKOUT, "checked out"), 
        (CHECKIN, "checked in"), 
        (REPAIR_OUT, "sent for repair"), 
        (REPAIR_BACK, "back from repair")]

    item = models.ForeignKey(Item)
    person = models.ForeignKey(Person, blank=True, null=True)  # for add and repair transactions, Person will be None
    timestamp = models.DateTimeField(blank=True, default=datetime.datetime.now)
    kind = models.IntegerField(blank=True, null=True, choices=TRANSACTION_KINDS)
    note = models.CharField(blank=True, null=True, max_length=250)
    
    class Admin:
        list_filter = ["kind", "timestamp", "person"]
        date_hierarchy = "timestamp"

    class Meta:
        ordering = ["-timestamp"]
        get_latest_by = "timestamp"

    def __unicode__(self):
        person = u" by %s " % self.person if self.person else u" "
        return u"%s %s%s(%s)" % (self.item, self.get_kind_display(), person, self.timestamp)


class Penalty(models.Model):
    """
    A record of a penalty assessed for returning equipment late.
    """
    BASE_PENALTY_AMOUNT = 2500  # Dollar-credits per day of late equipment
    
    student = models.ForeignKey(Person, limit_choices_to={'kind':STUDENT_KIND})
    when_levied = models.DateTimeField(default=datetime.datetime.now)
    items = models.ManyToManyField(Item, 
        help_text="Items that were most late at the time the penalty was levied (for reference).")
    amount = models.IntegerField(default=BASE_PENALTY_AMOUNT, 
        help_text="%s dollar credits per day of lateness" % BASE_PENALTY_AMOUNT)
    
    class Admin:
        list_display = ["student", "when_levied", "amount"]
        list_filter = ["when_levied", "student"]
        date_hierarchy = "when_levied"
        
    class Meta:
        ordering = ["-when_levied"]
        get_latest_by = "when_levied"
        verbose_name_plural = "penalties"
        
    def __unicode__(self):
        return u"%s, %s, $%s" % (self.student, self.when_levied, self.amount)

    def admin_url(self):
        return "/admin/equipment/penalty/%s/" % self.id

    @classmethod
    def levy(cls, student):
        """
        Levy the appropriate late-equipment penalty on the given person, creating
        a new Penalty object in the database. 
        
        Find the oldest overdue equipment, calculate its days_overdue, multiply by 
        BASE_PENALTY_AMOUNT, and record.
        
        If the method succeeds, it returns the penalty object.
        """
        equipment_lent = student.item_set.all()
        overdue_days = 0
        for item in equipment_lent:
            overdue_days = max(overdue_days, item.days_overdue())
        penalty_amount = cls.BASE_PENALTY_AMOUNT * overdue_days
        if penalty_amount == 0:
            return
        penalty = cls.objects.create(student=student, amount=penalty_amount)
        equipment_lent = student.item_set.all()
        for item in equipment_lent:
            if item.days_overdue() == overdue_days:
                penalty.items.add(item)
        penalty.save()
        return penalty
