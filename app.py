import os
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key') # Required for flash messages and sessions

# --- Database Configuration ---
db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

def get_db_connection():
    """Establishes a connection to the database."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        flash(f"Database Connection Error: {err}", "danger")
        print(f"Error connecting to database: {err}") # Log error
        return None

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Executes a SQL query and returns results."""
    conn = get_db_connection()
    if not conn:
        return None # Or raise an exception

    cursor = conn.cursor(dictionary=True) # Use dictionary cursor
    result = None
    try:
        cursor.execute(query, params or ())
        if commit:
            conn.commit()
            result = cursor.lastrowid
        elif fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Database Query Error: {err}", "danger")
        print(f"Query Error: {err}\nQuery: {query}\nParams: {params}") # Log error
        conn.rollback() # Rollback on error if changes were made
    finally:
        cursor.close()
        conn.close()
    return result

# --- Helper Functions ---
def get_room_details(room_id):
    query = """
        SELECT r.room_id, r.room_number, r.floor, rt.name as type_name, rt.cost_per_day, r.is_occupied
        FROM rooms r
        JOIN room_types rt ON r.type_id = rt.type_id
        WHERE r.room_id = %s
    """
    return execute_query(query, (room_id,), fetch_one=True)

def get_customer_details(customer_id):
    query = "SELECT * FROM customers WHERE customer_id = %s"
    return execute_query(query, (customer_id,), fetch_one=True)

def get_employee_details(employee_id):
     query = "SELECT * FROM employees WHERE employee_id = %s"
     return execute_query(query, (employee_id,), fetch_one=True)


# --- Routes ---
@app.route('/')
def index():
    """Homepage / Dashboard"""
    # Get availability summary
    available_rooms_query = """
        SELECT rt.name, COUNT(r.room_id) as count
        FROM rooms r
        JOIN room_types rt ON r.type_id = rt.type_id
        WHERE r.is_occupied = FALSE
        GROUP BY rt.name
    """
    total_rooms_query = """
        SELECT rt.name, COUNT(r.room_id) as count
        FROM rooms r
        JOIN room_types rt ON r.type_id = rt.type_id
        GROUP BY rt.name
    """
    available_counts = {row['name']: row['count'] for row in execute_query(available_rooms_query, fetch_all=True)}
    total_counts = {row['name']: row['count'] for row in execute_query(total_rooms_query, fetch_all=True)}

    availability = {}
    all_types = execute_query("SELECT name FROM room_types", fetch_all=True)
    if all_types:
        for type_info in all_types:
            type_name = type_info['name']
            total = total_counts.get(type_name, 0)
            available = available_counts.get(type_name, 0)
            availability[type_name] = {'available': available, 'total': total}

    return render_template('index.html', availability=availability)

# --- Room Management ---
@app.route('/rooms')
def view_rooms():
    """View all rooms and their status"""
    query = """
        SELECT r.room_id, r.room_number, r.floor, rt.name as type_name, rt.cost_per_day, r.is_occupied
        FROM rooms r
        JOIN room_types rt ON r.type_id = rt.type_id
        ORDER BY r.floor, r.room_number
    """
    rooms = execute_query(query, fetch_all=True)
    return render_template('rooms.html', rooms=rooms or [])

# --- Customer Management ---
@app.route('/customers')
def view_customers():
    """View currently checked-in customers"""
    query = """
        SELECT c.*, r.room_number
        FROM customers c
        LEFT JOIN rooms r ON c.assigned_room_id = r.room_id
        WHERE c.check_out_date IS NULL
        ORDER BY c.last_name, c.first_name
    """
    customers = execute_query(query, fetch_all=True)
    return render_template('customers.html', customers=customers or [])

@app.route('/customers/all')
def view_all_customers():
    """View all customers (including past)"""
    query = """
        SELECT c.*, r.room_number
        FROM customers c
        LEFT JOIN rooms r ON c.assigned_room_id = r.room_id
        ORDER BY c.check_in_date DESC, c.last_name
    """
    customers = execute_query(query, fetch_all=True)
    return render_template('customers_all.html', customers=customers or [])


@app.route('/customer/check_in', methods=['GET', 'POST'])
def check_in_customer():
    """Form to check in a new customer"""
    # Get available rooms
    available_rooms_query = """
        SELECT r.room_id, r.room_number, rt.name as type_name
        FROM rooms r
        JOIN room_types rt ON r.type_id = rt.type_id
        WHERE r.is_occupied = FALSE
        ORDER BY r.room_number
    """
    available_rooms = execute_query(available_rooms_query, fetch_all=True)

    if request.method == 'POST':
        passport = request.form['passport_number']
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name')
        city = request.form['city']
        check_in = request.form['check_in_date']
        room_id = request.form.get('room_id') # Use get to handle if no rooms available

        if not all([passport, last_name, first_name, city, check_in, room_id]):
            flash("All fields except middle name are required.", "warning")
            return render_template('customer_form.html', rooms=available_rooms or [], form_data=request.form, action="Check In")

        # Check if passport number already exists for a checked-in customer
        existing_customer_query = "SELECT 1 FROM customers WHERE passport_number = %s AND check_out_date IS NULL"
        if execute_query(existing_customer_query, (passport,), fetch_one=True):
             flash("A customer with this passport number is already checked in.", "danger")
             return render_template('customer_form.html', rooms=available_rooms or [], form_data=request.form, action="Check In")


        # Check if room is still available (race condition possible, use transaction ideally)
        room_status_query = "SELECT is_occupied FROM rooms WHERE room_id = %s"
        room = execute_query(room_status_query, (room_id,), fetch_one=True)
        if not room or room['is_occupied']:
            flash("Selected room is no longer available.", "warning")
            # Refresh available rooms list
            available_rooms = execute_query(available_rooms_query, fetch_all=True)
            return render_template('customer_form.html', rooms=available_rooms or [], form_data=request.form, action="Check In")

        # Use a transaction to ensure atomicity
        conn = get_db_connection()
        if not conn:
            return redirect(url_for('check_in_customer'))

        cursor = conn.cursor()
        try:
            # Insert Customer
            insert_customer_query = """
                INSERT INTO customers (passport_number, last_name, first_name, middle_name, city, check_in_date, assigned_room_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_customer_query, (passport, last_name, first_name, middle_name, city, check_in, room_id))

            # Update Room Status
            update_room_query = "UPDATE rooms SET is_occupied = TRUE WHERE room_id = %s"
            cursor.execute(update_room_query, (room_id,))

            conn.commit()
            flash(f"Customer {first_name} {last_name} checked into Room {request.form.get('room_number_display', room_id)} successfully!", "success") # Use display if passed
            return redirect(url_for('view_customers'))

        except mysql.connector.Error as err:
            conn.rollback()
            flash(f"Check-in failed: {err}", "danger")
            print(f"Check-in Error: {err}")
            # Refresh available rooms list
            available_rooms = execute_query(available_rooms_query, fetch_all=True)
            return render_template('customer_form.html', rooms=available_rooms or [], form_data=request.form, action="Check In")
        finally:
            cursor.close()
            conn.close()

    # GET request
    return render_template('customer_form.html', rooms=available_rooms or [], action="Check In", form_data={})

@app.route('/customer/check_out/<int:customer_id>', methods=['POST'])
def check_out_customer(customer_id):
    """Checks out a customer"""
    today = date.today().isoformat()
    customer = get_customer_details(customer_id)

    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for('view_customers'))

    if customer['check_out_date']:
         flash("Customer is already checked out.", "warning")
         return redirect(url_for('view_customers'))

    room_id = customer['assigned_room_id']

    # Use a transaction
    conn = get_db_connection()
    if not conn: return redirect(url_for('view_customers'))
    cursor = conn.cursor()
    try:
        # Update Customer Check-out Date
        update_customer_query = "UPDATE customers SET check_out_date = %s WHERE customer_id = %s"
        cursor.execute(update_customer_query, (today, customer_id))

        # Update Room Status
        if room_id: # Should always have a room if checked in
            update_room_query = "UPDATE rooms SET is_occupied = FALSE WHERE room_id = %s"
            cursor.execute(update_room_query, (room_id,))

        conn.commit()
        flash(f"Customer {customer['first_name']} {customer['last_name']} checked out successfully.", "success")
        return redirect(url_for('generate_invoice', customer_id=customer_id))


    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Check-out failed: {err}", "danger")
        print(f"Check-out Error: {err}")
        return redirect(url_for('view_customers'))
    finally:
        cursor.close()
        conn.close()

# --- Employee Management ---
@app.route('/employees')
def view_employees():
    """View all employees"""
    employees = execute_query("SELECT * FROM employees ORDER BY last_name, first_name", fetch_all=True)
    return render_template('employees.html', employees=employees or [])

@app.route('/employee/add', methods=['GET', 'POST'])
def add_employee():
    """Hire a new employee"""
    if request.method == 'POST':
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name')

        if not last_name or not first_name:
            flash("First name and last name are required.", "warning")
            return render_template('employee_form.html', action="Add", form_data=request.form)

        query = "INSERT INTO employees (last_name, first_name, middle_name) VALUES (%s, %s, %s)"
        employee_id = execute_query(query, (last_name, first_name, middle_name), commit=True)

        if employee_id is not None:
            flash(f"Employee {first_name} {last_name} hired successfully.", "success")
            return redirect(url_for('view_employees'))
        else:
             return render_template('employee_form.html', action="Add", form_data=request.form)


    return render_template('employee_form.html', action="Add", form_data={})

@app.route('/employee/delete/<int:employee_id>', methods=['POST'])
def delete_employee(employee_id):
    """Dismiss an employee"""
    # Check if employee exists before attempting delete
    employee = get_employee_details(employee_id)
    if not employee:
        flash("Employee not found.", "danger")
        return redirect(url_for('view_employees'))

    # Deletion will cascade to cleaning_schedule due to ON DELETE CASCADE
    query = "DELETE FROM employees WHERE employee_id = %s"
    execute_query(query, (employee_id,), commit=True)
    # Check if deletion actually happened
    flash(f"Employee {employee['first_name']} {employee['last_name']} dismissed.", "success")
    return redirect(url_for('view_employees'))


# --- Schedule Management ---
@app.route('/schedule')
def view_schedule():
    """View cleaning schedule"""
    query = """
        SELECT cs.schedule_id, e.first_name, e.last_name, cs.floor, cs.day_of_week
        FROM cleaning_schedule cs
        JOIN employees e ON cs.employee_id = e.employee_id
        ORDER BY cs.day_of_week, cs.floor, e.last_name
    """
    schedule = execute_query(query, fetch_all=True)
    employees = execute_query("SELECT employee_id, first_name, last_name FROM employees ORDER BY last_name", fetch_all=True)
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    # Get distinct floors from rooms table
    floors_query = "SELECT DISTINCT floor FROM rooms ORDER BY floor"
    floors_result = execute_query(floors_query, fetch_all=True)
    floors = [f['floor'] for f in floors_result] if floors_result else []


    return render_template('schedule.html',
                           schedule=schedule or [],
                           employees=employees or [],
                           days=days,
                           floors=floors)

@app.route('/schedule/add', methods=['POST'])
def add_schedule_entry():
    """Add a new entry to the cleaning schedule"""
    employee_id = request.form.get('employee_id')
    floor = request.form.get('floor')
    day = request.form.get('day_of_week')

    if not all([employee_id, floor, day]):
        flash("Employee, Floor, and Day are required.", "warning")
        return redirect(url_for('view_schedule'))

    # Check for duplicates
    check_query = "SELECT 1 FROM cleaning_schedule WHERE employee_id = %s AND floor = %s AND day_of_week = %s"
    if execute_query(check_query, (employee_id, floor, day), fetch_one=True):
         flash("This schedule entry (Employee, Floor, Day) already exists.", "warning")
         return redirect(url_for('view_schedule'))


    query = "INSERT INTO cleaning_schedule (employee_id, floor, day_of_week) VALUES (%s, %s, %s)"
    schedule_id = execute_query(query, (employee_id, floor, day), commit=True)

    if schedule_id is not None:
        flash("Schedule entry added successfully.", "success")
    else:
        pass # Redirect anyway
    return redirect(url_for('view_schedule'))

@app.route('/schedule/delete/<int:schedule_id>', methods=['POST'])
def delete_schedule_entry(schedule_id):
    """Delete a schedule entry"""
    query = "DELETE FROM cleaning_schedule WHERE schedule_id = %s"
    execute_query(query, (schedule_id,), commit=True)
    flash("Schedule entry deleted.", "success")
    return redirect(url_for('view_schedule'))

# --- Queries & Reports ---
@app.route('/reports')
def reports_page():
     """Page with forms for various queries"""
     # Data needed for forms
     rooms = execute_query("SELECT room_id, room_number FROM rooms ORDER BY room_number", fetch_all=True)
     customers = execute_query("SELECT customer_id, first_name, last_name FROM customers WHERE check_out_date IS NULL ORDER BY last_name", fetch_all=True)
     days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
     cities = execute_query("SELECT DISTINCT city FROM customers ORDER BY city", fetch_all=True)

     return render_template('reports.html',
                            rooms=rooms or [],
                            customers=customers or [],
                            days=days,
                            cities=[c['city'] for c in cities] if cities else [])

@app.route('/query/occupants_by_room', methods=['POST'])
def query_occupants_by_room():
    room_id = request.form.get('room_id')
    if not room_id:
        flash("Please select a room.", "warning")
        return redirect(url_for('reports_page'))

    query = """
        SELECT c.*, r.room_number
        FROM customers c
        JOIN rooms r ON c.assigned_room_id = r.room_id
        WHERE c.assigned_room_id = %s AND c.check_out_date IS NULL
    """
    results = execute_query(query, (room_id,), fetch_all=True)
    room = get_room_details(room_id)
    room_number = room['room_number'] if room else 'Unknown'
    flash(f"Showing occupants for Room {room_number}", "info")
    # Re-render reports page with results section
    session['query_results'] = results # Use session to pass results
    session['query_title'] = f"Occupants in Room {room_number}"
    return redirect(url_for('reports_page_with_results'))

@app.route('/query/customers_by_city', methods=['POST'])
def query_customers_by_city():
    city = request.form.get('city')
    if not city:
        flash("Please enter a city.", "warning")
        return redirect(url_for('reports_page'))

    query = """
        SELECT c.*, r.room_number
        FROM customers c
        LEFT JOIN rooms r ON c.assigned_room_id = r.room_id
        WHERE c.city = %s AND c.check_out_date IS NULL
        ORDER BY c.last_name, c.first_name
    """
    results = execute_query(query, (city,), fetch_all=True)
    flash(f"Showing current guests from {city}", "info")
    session['query_results'] = results
    session['query_title'] = f"Current Guests from {city}"
    return redirect(url_for('reports_page_with_results'))


@app.route('/query/cleaner_for_customer_stay', methods=['POST'])
def query_cleaner_for_customer_stay():
    customer_id = request.form.get('customer_id')
    day_of_week = request.form.get('day_of_week')

    if not customer_id or not day_of_week:
        flash("Please select a customer and a day of the week.", "warning")
        return redirect(url_for('reports_page'))

    # Find the customer's room and floor
    customer_query = """
        SELECT r.floor, r.room_number, c.first_name, c.last_name
        FROM customers c
        JOIN rooms r ON c.assigned_room_id = r.room_id
        WHERE c.customer_id = %s AND c.check_out_date IS NULL
    """
    customer_info = execute_query(customer_query, (customer_id,), fetch_one=True)

    if not customer_info:
        flash("Could not find active stay information for the selected customer.", "warning")
        return redirect(url_for('reports_page'))

    floor = customer_info['floor']
    customer_name = f"{customer_info['first_name']} {customer_info['last_name']}"
    room_number = customer_info['room_number']

    # Find the employee(s) cleaning that floor on that day
    cleaner_query = """
        SELECT e.first_name, e.last_name, e.middle_name
        FROM cleaning_schedule cs
        JOIN employees e ON cs.employee_id = e.employee_id
        WHERE cs.floor = %s AND cs.day_of_week = %s
    """
    results = execute_query(cleaner_query, (floor, day_of_week), fetch_all=True)
    flash(f"Showing cleaner(s) for Floor {floor} (Room {room_number}, Customer: {customer_name}) on {day_of_week}", "info")
    session['query_results'] = results
    session['query_title'] = f"Cleaner(s) for Floor {floor} on {day_of_week}"
    return redirect(url_for('reports_page_with_results'))


@app.route('/reports/results')
def reports_page_with_results():
    """Display the reports page with results stored in session"""
    results = session.pop('query_results', None) # Get and remove from session
    title = session.pop('query_title', 'Query Results')

    # Data needed for forms (same as reports_page)
    rooms = execute_query("SELECT room_id, room_number FROM rooms ORDER BY room_number", fetch_all=True)
    customers = execute_query("SELECT customer_id, first_name, last_name FROM customers WHERE check_out_date IS NULL ORDER BY last_name", fetch_all=True)
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    cities = execute_query("SELECT DISTINCT city FROM customers ORDER BY city", fetch_all=True)

    return render_template('reports.html',
                            rooms=rooms or [],
                            customers=customers or [],
                            days=days,
                            cities=[c['city'] for c in cities] if cities else [],
                            query_results=results,
                            query_title=title)


# --- Invoice Generation ---
@app.route('/invoice/<int:customer_id>')
def generate_invoice(customer_id):
    """Generate and display an invoice for a customer"""
    customer = get_customer_details(customer_id)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for('view_all_customers')) # Redirect to list of all customers

    if not customer['check_out_date']:
         check_out_date = date.today()
         flash("Warning: Customer has not checked out. Invoice calculated based on today's date.", "warning")
    else:
         check_out_date = customer['check_out_date']


    if not customer['assigned_room_id']:
         flash("Customer is not currently assigned to a room (may have already checked out without room info). Cannot calculate cost.", "danger")
         return redirect(url_for('view_all_customers'))


    room = get_room_details(customer['assigned_room_id'])
    if not room:
        flash("Room details not found for this customer's stay.", "danger")
        return redirect(url_for('view_all_customers'))

    check_in_date = customer['check_in_date']

    # Calculate duration (number of nights)
    # Ensure dates are date objects
    if isinstance(check_in_date, str): check_in_date = date.fromisoformat(check_in_date)
    if isinstance(check_out_date, str): check_out_date = date.fromisoformat(check_out_date)

    duration_delta = check_out_date - check_in_date
    duration_days = max(1, duration_delta.days) # Stay is at least 1 day/night

    cost_per_day = room['cost_per_day']
    total_cost = duration_days * cost_per_day

    invoice_data = {
        'customer': customer,
        'room': room,
        'check_in': customer['check_in_date'], # Display original check-in
        'check_out': check_out_date, # Display actual or calculated check-out
        'duration_days': duration_days,
        'total_cost': total_cost
    }

    today = date.today().isoformat()
    return render_template('invoice.html', invoice=invoice_data, today_date=today)

@app.route('/hotel_report')
def hotel_report():
    """Generate a report on room occupancy and total income"""
    report_data = {'occupancy': {}, 'income': 0.0}

    # --- Occupancy Report ---
    # Calculate how many days each room was occupied and free
    rooms_query = """
        SELECT r.room_number, r.is_occupied, rt.name as type_name
        FROM rooms r JOIN room_types rt ON r.type_id = rt.type_id
        ORDER BY r.room_number
    """
    all_rooms = execute_query(rooms_query, fetch_all=True)
    report_data['rooms_status'] = all_rooms

    # --- Income Report ---
    # Calculate total income from completed stays (where check_out_date is set)
    income_query = """
        SELECT
            c.customer_id,
            c.check_in_date,
            c.check_out_date,
            rt.cost_per_day
        FROM customers c
        JOIN rooms r ON c.assigned_room_id = r.room_id -- Use the room assigned during stay
        JOIN room_types rt ON r.type_id = rt.type_id
        WHERE c.check_out_date IS NOT NULL
          AND c.check_in_date IS NOT NULL
          AND c.assigned_room_id IS NOT NULL
    """
    completed_stays = execute_query(income_query, fetch_all=True)

    total_income = 0.0
    if completed_stays:
        for stay in completed_stays:
            try:
                check_in = stay['check_in_date']
                check_out = stay['check_out_date']
                cost = stay['cost_per_day']

                # Ensure dates are date objects
                if isinstance(check_in, str): check_in = date.fromisoformat(check_in)
                if isinstance(check_out, str): check_out = date.fromisoformat(check_out)

                duration_delta = check_out - check_in
                duration_days = max(1, duration_delta.days) # Min 1 day charge
                total_income += float(duration_days * cost)
            except Exception as e:
                 print(f"Error calculating income for stay customer_id {stay.get('customer_id', 'N/A')}: {e}")

    report_data['total_income'] = round(total_income, 2)

    return render_template('hotel_report.html', report=report_data)

if __name__ == '__main__':
    # Ensure database exists? Could add a check here.
    app.run(debug=True)