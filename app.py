from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
import psycopg2
import os
import re
import psycopg2.extras
import bcrypt

def create_app():
    app = Flask(__name__)
    return app
app = Flask(__name__)

app.secret_key = 'mwambui'  # Add a secret key for sessions

# Database Configuration
DATABASE_URL = "postgresql://postgres:r2d2c3po@localhost:5432/dhub"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# Function to get a database connection
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if date is None:
        return ""
    if fmt is None:
        fmt = "%Y-%m-%d"
    return date.strftime(fmt)

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, id, email, role, institution_id=None):
        self.id = id
        self.email = email
        self.role = role
        self.institution_id = institution_id

@login_manager.user_loader
def load_user(user_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, role, institution_id FROM users WHERE id = %s;", (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return User(
                id=user_data[0],
                email=user_data[1],
                role=user_data[2],
                institution_id=user_data[3]
            )
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # If user is already logged in, redirect appropriately
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT institution_id FROM users WHERE id = %s;", (current_user.id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result and result[0]:
            return redirect(url_for('my_institution'))
        else:
            return redirect(url_for('register_institution'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Retrieve user from the database
            cur.execute("SELECT id, email, password, role, institution_id FROM users WHERE email = %s;", (email,))
            user_data = cur.fetchone()

            if user_data:
                user_id = user_data[0]
                user_email = user_data[1]
                hashed_password = user_data[2]
                user_role = user_data[3]
                institution_id = user_data[4]

                # Verify the password
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
                    user = User(id=user_id, email=user_email, role=user_role)
                    login_user(user)
                    flash('Logged in successfully!', 'success')

                    # Redirect based on institution status
                    next_page = request.args.get('next')
                    if next_page:
                        return redirect(next_page)
                    elif institution_id:
                        return redirect(url_for('my_institution'))
                    else:
                        return redirect(url_for('register_institution'))
                else:
                    flash('Invalid email or password.', 'danger')
                    return render_template('login.html', email=email)
            else:
                flash('Invalid email or password.', 'danger')
                return render_template('login.html', email=email)

        except Exception as e:
            print(f"An error occurred during login: {e}")
            flash('An error occurred during login. Please try again.', 'danger')
            return render_template('login.html', email=email)

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # GET request: Display login form
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/institutions', methods=['GET'])
def institutions():
    conn = None
    cur = None
    institutions_list = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch all institutions
        cur.execute("SELECT id, name, location, email, phone, website, type, photo_filename FROM institutions;")
        institutions_data = cur.fetchall()  # Fetch institution data

        # For each institution, fetch their needed items from institution_needed_items
        for institution_row in institutions_data:
            institution_id = institution_row[0]  # Get the institution id
            cur.execute("""
                SELECT i.name
                FROM items i
                JOIN institution_needed_items ini ON i.id = ini.item_id
                WHERE ini.institution_id = %s;
            """, (institution_id,))
            needed_items = [row[0] for row in cur.fetchall()]  # Fetch all items for this institution

            institution_dict = {
                'id': institution_row[0],
                'name': institution_row[1],
                'location': institution_row[2],
                'email': institution_row[3],
                'phone': institution_row[4],
                'website': institution_row[5],
                'type': institution_row[6],
                'photo_filename': institution_row[7],
                'needed_items': needed_items
            }
            institutions_list.append(institution_dict)

    except (psycopg2.Error, Exception) as e:
        print(f"Error fetching institutions and items: {e}")
        institutions_list = []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template('institutions.html', institutions=institutions_list)

@app.route('/donate/<int:institution_id>', methods=['GET', 'POST'])
def donate(institution_id):
    conn = None
    cur = None
    institution = None
    items = []

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if request.method == 'GET':
            cur.execute("SELECT id, name FROM institutions WHERE id = %s;", (institution_id,))
            institution_data = cur.fetchone()
            if institution_data:
                institution = {'id': institution_data['id'], 'name': institution_data['name']}
            else:
                flash("Institution not found.", "danger")
                return redirect(url_for('institutions'))

            cur.execute("SELECT id, name FROM items WHERE name NOT IN ('Cash', 'Service') ORDER BY name;")
            items_data = cur.fetchall()
            items = [{'id': row['id'], 'name': row['name']} for row in items_data]

            return render_template('donate.html', institution=institution, items=items)

        elif request.method == 'POST':
            # Make sure these names match your HTML form field names!
            donor_name = request.form.get('donor_name')
            donor_email = request.form.get('donor_email')
            donor_phone = request.form.get('donor_phone')
            donor_type = request.form.get('donor_type')
            donation_type = request.form.get('donation_type')
            message = request.form.get('message')

            if not donor_name:
                flash("Name is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))
            if not donor_email:
                flash("Email is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))
            if not donor_phone:
                flash("Phone number is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))
            if not donor_type:
                flash("Donor type is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))
            if not donation_type:
                flash("Donation type is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))

            donation_amount = None
            item_id = None
            item_quantity = None
            item_condition = None
            service_description = None

            if donation_type == 'cash':
                donation_amount = request.form.get('donation_amount')
                if not donation_amount or float(donation_amount) <= 0:
                    flash("Please enter a valid donation amount.", "warning")
                    return redirect(url_for('donate', institution_id=institution_id))
                donation_amount = float(donation_amount)

            elif donation_type == 'item':
                item_id = request.form.get('item_id')
                item_quantity = request.form.get('item_quantity')
                item_condition = request.form.get('item_condition')

                if not item_id or not item_quantity or int(item_quantity) <= 0:
                    flash("Please select an item and enter a valid quantity.", "warning")
                    return redirect(url_for('donate', institution_id=institution_id))
                item_id = int(item_id)
                item_quantity = int(item_quantity)

            elif donation_type == 'service':
                service_description = request.form.get('service_description')
                if not service_description or not service_description.strip():
                    flash("Please provide a description of the service.", "warning")
                    return redirect(url_for('donate', institution_id=institution_id))

            else:
                flash("Invalid donation type selected.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))

            cur.execute(
                """
                INSERT INTO donations (
                    institution_id, donor_name, donor_email, donor_phone, donor_type,
                    donation_type, donation_amount, item_id, item_quantity,
                    item_condition, service_description, message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    institution_id, donor_name, donor_email, donor_phone, donor_type,
                    donation_type, donation_amount, item_id, item_quantity,
                    item_condition, service_description, message
                )
            )

            conn.commit()

            flash("Thank you for your donation!", "success")
            return redirect(url_for('institutions'))

    except (psycopg2.Error, Exception) as e:
        if conn:
            conn.rollback()
        print(f"An error occurred during donation: {e}")
        flash("An error occurred during your donation. Please try again.", "danger")
        return redirect(url_for('donate', institution_id=institution_id))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/edit_institution/<int:institution_id>', methods=['GET', 'POST'])
def edit_institution(institution_id):
    conn = None
    cur = None
    institution = None
    all_items = [] # To store all possible items for the checkbox list
    needed_items_ids = [] # To store the IDs of items the institution currently needs

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- GET Request: Display the edit form ---
        if request.method == 'GET':
            # Fetch institution details using explicit column names
            cur.execute("SELECT id, name, location, email, phone, website, type, photo_filename, created_at FROM institutions WHERE id = %s;", (institution_id,))
            institution_data = cur.fetchone()

            if institution_data:
                institution = {
                    'id': institution_data[0],
                    'name': institution_data[1],
                    'location': institution_data[2],
                    'email': institution_data[3],
                    'phone': institution_data[4],
                    'website': institution_data[5],
                    'type': institution_data[6],
                    'photo_filename': institution_data[7],
                    'created_at': institution_data[8]
                }
            else:
                flash("Institution not found.", "danger")
                return redirect(url_for('institutions'))

            # Fetch all possible items for the checkbox list
            cur.execute("SELECT id, name FROM items ORDER BY name;")
            all_items_data = cur.fetchall()
            all_items = [{'id': row[0], 'name': row[1]} for row in all_items_data]

            # Fetch the IDs of items this institution currently needs
            cur.execute("SELECT item_id FROM institution_needed_items WHERE institution_id = %s;", (institution_id,))
            needed_items_ids_data = cur.fetchall()
            needed_items_ids = [row[0] for row in needed_items_ids_data]


            return render_template(
                'edit_institution.html',
                institution=institution,
                all_items=all_items,
                needed_items_ids=needed_items_ids
            )

        # --- POST Request: Process the form submission and update ---
        elif request.method == 'POST':
            # Get form data
            name = request.form['name']
            institution_type = request.form['type']
            location = request.form.get('location')
            phone = request.form.get('phone')
            email = request.form.get('email')
            website = request.form.get('website')
            # photo_filename is handled separately below if a new file is uploaded


            # Validate required fields
            if not name or not institution_type:
                flash("Name and Institution Type are required.", "warning")

                # Improved Error Handling: Use request.form data and refetch only necessary data

                # Create a dictionary with submitted form data to pre-fill the template
                institution_for_error = {
                    'id': institution_id,
                    'name': request.form.get('name', ''),
                    'location': request.form.get('location', ''),
                    'phone': request.form.get('phone', ''),
                    'email': request.form.get('email', ''),
                    'website': request.form.get('website', ''),
                    'type': request.form.get('type', '')
                }

                # Fetch the existing photo_filename from the database to display on the error page
                existing_institution_data = None
                cur.execute("SELECT photo_filename FROM institutions WHERE id = %s;", (institution_id,))
                existing_institution_data = cur.fetchone()

                if existing_institution_data:
                    institution_for_error['photo_filename'] = existing_institution_data[0]
                else:
                    # If for some reason the institution is not found here, handle that
                    institution_for_error['photo_filename'] = None


                # Refetch all possible items for the checkbox list
                cur.execute("SELECT id, name FROM items ORDER BY name;")
                all_items_data_for_error = cur.fetchall()
                all_items_for_error = [{'id': row[0], 'name': row[1]} for row in all_items_data_for_error]

                # Get the selected needed items from the current form submission
                needed_items_ids_for_error = [int(item_id) for item_id in request.form.getlist('needed_items') if item_id.isdigit()]

                # Handle the 'other' needed item if it was checked in the failed submission
                if 'other' in request.form.getlist('needed_items'):
                     institution_for_error['other_item_spec'] = request.form.get('other_item_spec', '')


                return render_template(
                    'edit_institution.html',
                    institution=institution_for_error,
                    all_items=all_items_for_error,
                    needed_items_ids=needed_items_ids_for_error
                )


            # Handle photo upload (if a new file is provided)
            photo = request.files.get('photo')
            # Fetch current photo filename before potential update
            cur.execute("SELECT photo_filename FROM institutions WHERE id = %s;", (institution_id,))
            current_photo_filename_data = cur.fetchone()
            photo_filename = current_photo_filename_data[0] if current_photo_filename_data else None # Keep existing filename by default

            if photo and photo.filename:
                # Secure the filename
                photo_filename = secure_filename(photo.filename)
                upload_folder = app.config['UPLOAD_FOLDER']
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                photo_path = os.path.join(upload_folder, photo_filename)
                photo.save(photo_path)

                # Optionally, delete the old photo file if it exists and is different
                if photo_filename != current_photo_filename_data[0] and current_photo_filename_data[0]:
                    old_photo_path = os.path.join(upload_folder, current_photo_filename_data[0])
                    if os.path.exists(old_photo_path):
                        try:
                            os.remove(old_photo_path)
                        except Exception as e:
                            print(f"Could not remove old photo: {e}")

            # Update institution details in the database
            cur.execute(
                """
                UPDATE institutions SET
                    name = %s, location = %s, phone = %s,
                    email = %s, website = %s, photo_filename = %s, type = %s
                WHERE id = %s AND user_id = %s;
                """,
                (
                    name, location, phone, email, website,
                    photo_filename, institution_type, institution_id, current_user.id
                )
            )

            # Update needed items:
            # 1. Delete existing needed items for this institution
            cur.execute("DELETE FROM institution_needed_items WHERE institution_id = %s;", (institution_id,))

            # 2. Insert the newly selected needed items
            needed_items = request.form.getlist('needed_items') # Get list of selected item IDs

            # Get 'other' item specification if 'other' was selected
            other_item_spec = request.form.get('other_item_spec')

            for item_id_str in needed_items:
                if item_id_str.isdigit(): # Only process if it's a digit (an item ID)
                    item_id = int(item_id_str)
                    # Insert into institution_needed_items table
                    cur.execute(
                        "INSERT INTO institution_needed_items (institution_id, item_id) VALUES (%s, %s);",
                        (institution_id, item_id)
                    )
                elif item_id_str == 'other': # Handle 'other' checkbox specifically
                        if other_item_spec:
                            # Check if an item with this specification already exists
                            cur.execute("SELECT id FROM items WHERE name = %s;", (other_item_spec,))
                            existing_item = cur.fetchone()

                            item_id_to_link = None
                            if existing_item:
                                # If it exists, get its ID
                                item_id_to_link = existing_item[0]
                            else:
                                # If not, insert a new item
                                cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id;", (other_item_spec,))
                                newly_inserted_item = cur.fetchone()
                                if newly_inserted_item:
                                    item_id_to_link = newly_inserted_item[0]
                                else:
                                    # Handle potential error if insertion failed
                                    flash(f"Error adding new item '{other_item_spec}'.", "danger")
                                    continue # Skip linking for this item

                            # Link the institution to this item (either existing or new)
                            if item_id_to_link:
                                cur.execute(
                                    "INSERT INTO institution_needed_items (institution_id, item_id) VALUES (%s, %s);",
                                    (institution_id, item_id_to_link)
                                )
                        else:
                            # Optionally handle the case where 'other' is checked but the specification is empty
                            flash("'Other' item checkbox was selected, but no specification was provided.", "warning")


            conn.commit()

            flash(f"Institution '{name}' updated successfully!", "success")
            # Redirect to the institution's profile page (assuming you have a 'my_institution' route)
            return redirect(url_for('my_institution', institution_id=institution_id))
            # Alternatively, redirect to the institutions list:
            # return redirect(url_for('institutions'))


    except (psycopg2.Error, Exception) as e:
        if conn:
            conn.rollback()
        print(f"An error occurred during institution update: {e}") # Print the actual error for debugging
        flash("An error occurred while updating the institution. Please try again.", "danger")
        # ... (code for updating institution details) ...
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/my_institution')
@login_required
def my_institution():
    conn = None
    cur = None
    institution = None
    donations = []
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Fetch institution by user_id (not by users.institution_id)
        cur.execute("""
            SELECT *
            FROM institutions
            WHERE user_id = %s;
        """, (current_user.id,))
        institution = cur.fetchone()

        if not institution:
            flash("No institution found for your account.", "warning")
            return redirect(url_for('index'))
        # Get needed items for this institution

        cur.execute("""
            SELECT i.name
            FROM items i
            JOIN institution_needed_items ini ON i.id = ini.item_id
            WHERE ini.institution_id = %s;
        """, (institution['id'],))
        needed_items = [row[0] for row in cur.fetchall()]
        print("DEBUG: needed_items =", needed_items)

        # Get donations for this institution
        cur.execute("""
            SELECT d.donor_name, d.donor_email, d.donation_type, d.donation_amount, d.item_quantity, i.name AS item_name, d.item_condition, d.service_description, d.donation_date
            FROM donations d
            LEFT JOIN items i ON d.item_id = i.id
            WHERE d.institution_id = %s
            ORDER BY d.donation_date DESC;
        """, (institution['id'],))
        donations = cur.fetchall()

    except Exception as e:
        flash("Error loading institution data.", "danger")
        print(e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template('my_institution.html', institution=institution, donations=donations, needed_items=needed_items)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Basic validation
        if not email or not password or not confirm_password:
            flash('All fields are required.', 'warning')
            return render_template('register.html', email=email) # Pass email back to pre-fill

        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return render_template('register.html', email=email)

        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Check if user with this email already exists
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            existing_user = cur.fetchone()
            if existing_user:
                flash('Email address already registered.', 'warning')
                return render_template('register.html', email=email)

            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            # Insert new user into the database
            cur.execute(
                "INSERT INTO users (email, password) VALUES (%s, %s);",
                (email, hashed_password.decode('utf-8')) # Store hashed password as string
            )
            conn.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"An error occurred during registration: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', email=email) # Pass email back

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # GET request: Display registration form
    return render_template('register.html')

@app.route('/register_institution', methods=['GET', 'POST'])
@login_required
def register_institution():
    conn = None
    cur = None
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            name = request.form['name'].strip()
            email = request.form['email'].strip()
            phone = request.form['phone'].strip()
            location = request.form['location'].strip()
            institution_type = request.form['type']
            website = request.form.get('website', '').strip()
            needed_items = request.form.getlist('needed_items')
            other_item_spec = request.form.get('other_item_spec', '').strip()

            # Validation
            if not name or not email or not phone or not location or not institution_type:
                flash("All fields except website and photo are required.", "warning")
                return render_template('register_institution.html')

            # Email format validation
            email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_regex, email):
                flash("Please enter a valid email address.", "warning")
                return render_template('register_institution.html')

            photo = request.files.get('photo')
            photo_filename = None
            if photo and photo.filename:
                upload_folder = 'static/uploads'
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                photo_filename = photo.filename
                photo_path = os.path.join(upload_folder, photo_filename)
                photo.save(photo_path)

            # Insert institution data (with user_id)
            cur.execute(
                "INSERT INTO institutions (name, location, email, phone, website, type, photo_filename, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;",
                (name, location, email, phone, website, institution_type, photo_filename, current_user.id)
            )
            institution_id = cur.fetchone()[0]

            # Insert needed items and handle "Other"
            if needed_items:
                item_names = needed_items
                if 'other' in item_names and other_item_spec:
                    item_names.remove('other')
                    item_names.append(other_item_spec)

                processed_item_ids = []
                for item_name in item_names:
                    cur.execute("SELECT id FROM items WHERE name = %s;", (item_name,))
                    item_row = cur.fetchone()
                    if item_row:
                        processed_item_ids.append(item_row[0])
                    else:
                        cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id;", (item_name,))
                        processed_item_ids.append(cur.fetchone()[0])

                for item_id in processed_item_ids:
                    cur.execute(
                        "INSERT INTO institution_needed_items (institution_id, item_id) VALUES (%s, %s);",
                        (institution_id, item_id)
                    )

            # Optionally, update user's institution_id if you want a direct link
            cur.execute("UPDATE users SET institution_id = %s WHERE id = %s;", (institution_id, current_user.id))

            conn.commit()
            flash("Institution registered successfully!", "success")
            return redirect(url_for('my_institution'))

        except (psycopg2.Error, Exception) as e:
            if conn:
                conn.rollback()
            print(f"An error occurred during registration: {e}")
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template('register_institution.html')
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    return render_template('register_institution.html')

if __name__ == '__main__':
    app.run(debug=True)