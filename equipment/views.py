import datetime
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import loader, Context
from infoserver.equipment.models import ItemType, Item, ItemError, Penalty, Transaction, TransactionError
from infoserver.infobase.models import Person, STUDENT_KIND, PHASE_END_DATES, phase_for_cohort_and_date


def recent_transactions(person, number=6, hours=1, kind=None):
    """Fetch recent transactions by this person"""
    cutoff_datetime = datetime.datetime.now() - datetime.timedelta(hours=hours)
    checkouts = person.transaction_set.filter(kind=kind, timestamp__gte=cutoff_datetime)
    items = [c.item for c in checkouts[:number]]
    return items


def admin_access_allowed(user):
    """Does the user have the right permissions to be using this app?"""
    if user:
        return bool(user.groups.filter(name="equipment_tracker").count())


def render_response(template, var_dict, mimetype, filename):
    """Simple substitute for render_to_response (backporting some Django-1.0 stuff)"""
    t = loader.get_template(template)
    c = Context(var_dict)
    response = HttpResponse(t.render(c), mimetype=mimetype)
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    return response


@user_passes_test(admin_access_allowed)
def home(request):
    """Equipment app home page"""
    title = "Main Menu"
    message = "Welcome to the equipment tracker."
    return render_to_response("home.html", locals())


@user_passes_test(admin_access_allowed)
def check_in(request):
    """
    GET: Show check-in form.
    POST: Check in the scanned item.
    """
    title = "Check in"
    if request.method == "POST":
        number = request.POST['number']
        try:
            item = Item.find_by_number(number)
            person = item.checked_out_by
            title = "Checked in %s" % item
            if item.days_overdue():
                title += " (OVERDUE)"
            item.check_in()
            message = item.transaction_set.latest()
            recent_checkins = recent_transactions(person, kind=Transaction.CHECKIN)
        except (ItemError, TransactionError), error_message:
            pass
    return render_to_response("checkin.html", locals())


def checkout_url(request, due_timestamp, person_id):
    """
    Helper method that builds a URL to be used in a redirect. It will either have both 
    due-timestamp and user ID number, or just user ID number. If GET values are provided
    in `request`, for `due_timestamp` or `person_id`, they override the corresponding
    passed arguments.
    """
    if set(["due_date", "due_time"]).issubset(request.GET):
        due_timestamp = (request.GET['due_date'] + "-" + request.GET['due_time']).replace(":", "-")

    if due_timestamp:
        url_template = "/equipment/checkout/%s/%%s/" % due_timestamp
    else:
        url_template = "/equipment/checkout/%s/"

    if "person_id" in request.GET:
        person_id = request.GET['person_id']
        if Person.objects.filter(id_number=person_id).count() == 0:
            raise Person.DoesNotExist("UNKNOWN")
    url = url_template % person_id
    return url


@user_passes_test(admin_access_allowed)
def check_out(request, person_id=None, due_timestamp=None):
    """
    This view handles all stages of the checkout operation. In order for checkout to begin,
    a person_id must be in the URL. Optional due_timestamp is also in the URL. Those are 
    designed to persist; i.e. if you change the person the custom due date (if any) is 
    kept, and if you change the due date the person (if any) is kept.
    """
    # Set default due date values for use in "Change due date" form
    dummy_item = Item()
    dummy_item.set_due_datetime()
    example_due_date = dummy_item.due.date()
    example_due_time = dummy_item.due.time()
    # If a specific due-date was requested, set it
    if due_timestamp:
        custom_due_datetime = datetime.datetime.strptime(due_timestamp, "%Y-%m-%d-%H-%M")
    else:
        custom_due_datetime = None
    title = "Scan ID"

    try:
        # If a change is requested for person or due date, update the URL
        if set(["due_date", "due_time", "person_id"]).intersection(request.GET):
            url = checkout_url(request, due_timestamp, person_id)
            return HttpResponseRedirect(url)
        if person_id:
            person = Person.objects.get(id_number=person_id)
            if not person.is_active():
                raise Person.DoesNotExist("ID EXPIRED")
            title = "Checking out equipment to %s" % person
            recent_checkouts = recent_transactions(person, kind=Transaction.CHECKOUT)
        if request.method == "POST" and request.POST['number']:
            try:
                item = Item.find_by_number(request.POST['number'])
                item.check_out(person, custom_due_datetime)
                message = "Checked out %s" % item
                soundfile = "Glass.aiff"
            except (ItemError, TransactionError), error_message:
                soundfile = "error.mp3"
    except Person.DoesNotExist, reason:
        title = "Bad ID"
        id_number = person_id or request.GET['person_id']
        error_message = "%s: %s" % (id_number, reason)
        person = None
        soundfile = "error.mp3"
    return render_to_response("checkout.html", locals())


@user_passes_test(admin_access_allowed)
def item(request):
    """Display information on the specified item, with some editing options."""
    title = "Find an item"
    if 'number' in request.GET:
        number = request.GET['number']
        try:
            item = Item.find_by_number(number)
            title = unicode(item)
            history = item.transaction_set.all()
        except ItemError, error_message:
            pass
    else:
        message = "Type or scan the item's HIP number or serial number"
    return render_to_response("item.html", locals())


@user_passes_test(admin_access_allowed)
def person(request):
    """
    Display information on the specified borrower (person)
    """
    title = "Find a person"
    if 'person_id' in request.GET:
        person_id = request.GET['person_id']
        try:
            person = Person.objects.get(id_number=person_id)
            title = unicode(person)
            checked_out_items = person.item_set.all()
            transaction_history = person.transaction_set.all()
        except Person.DoesNotExist:
            error_message = "No person with id number %s" % person_id
    else:
        message = "Enter or scan the person's ID number"
        people = Person.objects.enrolled()  # For clickable list of names
    return render_to_response("person.html", locals())

def _penalty_report_data(cohort, phase=None):
    """
    Data rows for late-equipment report
    """
    if phase is None:
        phase = phase_for_cohort_and_date(cohort, datetime.date.today())
    else:
        phase = int(phase)
    if phase < 2 or phase > 4:
        raise ValueError
    start_date = PHASE_END_DATES[cohort][phase-1]
    end_date = PHASE_END_DATES[cohort][phase]
    all_penalties = Penalty.objects.filter(when_levied__range=(start_date, end_date))
    rows = [("Firstname", "Lastname", "ID number", "Date", "Amount")]
    rows += [(p.student.firstname, p.student.lastname, p.student.id_number, p.when_levied, 0-p.amount) for p in all_penalties]
    return rows

@user_passes_test(admin_access_allowed)
def report(request, report_kind=None, number=None):
    """
    General-purpose reporting view. To add a new report type, add an appropriate `if`
    clause here, and a corresponding `{% if ... %}` clause in the template for display.
    """
    if report_kind:
        now = datetime.datetime.now()
        title = "%s Report" % report_kind.title()
        try:
            if report_kind == "kits":
                kits = Item.objects.filter(itemtype__kit=True)
            if report_kind == "item":
                item = Item.find_by_number(number)
                title = item
            if report_kind == "instock":
                itemtypes = [i for i in ItemType.objects.all() if i.how_many_in_stock()]
            if report_kind == "latepenalties":
                try:
                    report_rows = _penalty_report_data(cohort=1, phase=number)
                    csv_link = "/equipment/report/latepenalties-csv/"
                    filename = "late_equipment.csv"
                except ValueError:
                    report_rows = None
                    error_message = "Can't generate report (incorrect phase?)"
            if report_kind.startswith("out-"):
                items = Item.objects.filter(status=Item.OUT, part_of_kit__isnull=True).order_by("due")
            if report_kind.startswith("overdue-"):
                items = Item.objects.filter(status=Item.OUT, due__lt=now, part_of_kit__isnull=True).order_by("due","checked_out_by")
                
            if report_kind.endswith("-student"):
                items = items.filter(checked_out_by__kind=STUDENT_KIND)
            if report_kind.endswith("-staff"):
                items = items.exclude(checked_out_by__kind=STUDENT_KIND)
        except ItemError, error_message:
            pass  # Letting error_message get picked up by the template
    else:
        title = "Reports"
    if report_kind and report_kind.endswith("-csv") and report_rows:
        return render_response("csv.html", locals(), mimetype="text/csv", filename=filename)
    else:
        return render_to_response("report.html", locals())


@user_passes_test(admin_access_allowed)
def find(request):
    """Control panel for finding items"""
    return render_to_response("find.html", locals())


@user_passes_test(admin_access_allowed)
def add(request):
    """Interface for adding new items to the system."""
    title = "Add, edit, or delete equipment items"
    return render_to_response("add.html", locals())


@user_passes_test(admin_access_allowed)
def buildkit(request, kit_id=None):
    """
    Helper view for building up kits. If no kit ID is passed, we ask for a kit. 
    If a kit ID is passed (via URL), we ask for items to add.
    Workflow: Create (empty) kits in admin; come to this view and add items
    """
    if "kit_id" in request.GET:
        return HttpResponseRedirect("/equipment/buildkit/%s/" % request.GET['kit_id'])
    title = "Enter/scan kit ID number"
    if kit_id:
        try:
            kit = Item.find_by_number(kit_id)
            assert(kit.itemtype.kit==True)
            title = "Adding equipment to %s" % kit
        except (Item.DoesNotExist, AssertionError):
            raise Http404
    if request.method == "POST":
        number = request.POST['number']
        item = Item.find_by_number(number)
        try:
            assert(item.itemtype.kit==False)  # Don't add a kit to a kit
            assert(item.part_of_kit==None)  # Item must not already be in a kit
            kit.contents.add(item)
            message = "Added %s" % item
        except ItemError, error_message:
            pass
    return render_to_response("buildkit.html", locals())


@user_passes_test(admin_access_allowed)
def penalty_statement(request, person_id):
    """
    Present a printable statement of dollar-credit penalties accrued due to late equipment.
    Also helps create that statement (presenting list of overdue equipment with a submit button).
    """
    if person_id:
        try:
            person = Person.objects.get(id_number=person_id)
        except Person.DoesNotExist:
            return Http404
        if request.method == "POST":
            new_penalty = Penalty.levy(person)
            message = "$%s penalty levied" % new_penalty.amount
        else:
            current_phase = phase_for_cohort_and_date(person.student_cohort, datetime.date.today())
            phase_start = PHASE_END_DATES[person.student_cohort][current_phase - 1]
            penalties = person.penalty_set.filter(when_levied__gte=phase_start)
            total = sum(p.amount for p in penalties)
            overduesies = Item.objects.filter(status=Item.OUT, due__lt=datetime.datetime.now(), checked_out_by=person).order_by("due")
            # If overdue items have already been charged in a penalty, don't show them
            for penalty in penalties:
                if set(i.id for i in overduesies) == set(i.id for i in penalty.items.all()):
                    overduesies = None
                    break
    else:  # If no person_id is passed, template can display a list
        people = Person.objects.enrolled()
    return render_to_response("penalty_statement.html", locals())
