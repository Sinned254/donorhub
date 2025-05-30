from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
import psycopg2
import os
import re
import psycopg2.extras
import bcrypt
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
from math import ceil


def create_app():
    app = Flask(__name__)
    return app
app = Flask(__name__)

app.secret_key = 'mwambui'  # Add a secret key for sessions
serializer = URLSafeTimedSerializer(app.secret_key)

app.permanent_session_lifetime = timedelta(minutes=5) 
@app.before_request
def make_session_permanent():
    session.permanent = True

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

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'charityhubconnect@gmail.com'         # <-- your Gmail address
app.config['MAIL_PASSWORD'] = 'qrdizbrhxsybqjvw'            # <-- your Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = 'charityhubconnect@gmail.com'   # <-- your Gmail address

mail = Mail(app)

def is_strong_password(password):
    if (len(password) < 8 or
        not re.search(r'[A-Z]', password) or
        not re.search(r'[a-z]', password) or
        not re.search(r'\d', password) or
        not re.search(r'[!@#$%^&*(),.?":{}|<>]', password)):
        return False
    return True

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
    # If user is already logged in, redirect based on role
        if hasattr(current_user, 'role') and current_user.role == 'admin':
            return redirect(url_for('admin'))
        elif hasattr(current_user, 'institution_id') and current_user.institution_id:
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
            cur.execute("SELECT id, email, password, role, institution_id, confirmed FROM users WHERE email = %s;", (email,))
            user_data = cur.fetchone()

            if user_data:
                user_id = user_data[0]
                user_email = user_data[1]
                hashed_password = user_data[2]
                user_role = user_data[3]
                institution_id = user_data[4]
                is_confirmed = user_data[5]

                if not is_confirmed:
                    flash('Your account is not confirmed. Please check your email for the confirmation link.', 'warning')
                    return render_template('login.html', email=email)

                # Verify the password
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
                    user = User(id=user_id, email=user_email, role=user_role)
                    login_user(user)
                    flash('Logged in successfully!', 'success')

                    # Redirect based on institution status
                    # Redirect based on user role and institution status
                    # Redirect based on user role and institution status
                    next_page = request.args.get('next')
                    if next_page:
                        return redirect(next_page)
                    elif user_role == 'admin':
                        return redirect(url_for('admin'))
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

@app.route('/admin')
@login_required
def admin():
    user_search = request.args.get('user_search', '').strip()
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Pending institutions with submitter's email
    cur.execute("""
        SELECT i.*, u.email AS submitted_by_email
        FROM institutions i
        LEFT JOIN users u ON i.user_id = u.id
        WHERE i.approved = FALSE
        ORDER BY i.created_at DESC;
    """)
    pending_institutions = cur.fetchall()

    # User search
    if user_search:
        cur.execute("""
            SELECT u.id, u.email, u.role, i.name AS institution_name
            FROM users u
            LEFT JOIN institutions i ON i.user_id = u.id
            WHERE u.first_name ILIKE %s OR u.last_name ILIKE %s OR u.email ILIKE %s
            ORDER BY u.role, u.email;
        """, (f'%{user_search}%', f'%{user_search}%', f'%{user_search}%'))
    else:
        cur.execute("""
            SELECT u.id, u.email, u.role, i.name AS institution_name
            FROM users u
            LEFT JOIN institutions i ON i.user_id = u.id
            ORDER BY u.role, u.email;
        """)
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'admin.html',
        pending_institutions=pending_institutions,
        users=users
    )

@app.route('/admin/approve/<int:institution_id>', methods=['POST'])
@login_required
def approve_institution(institution_id):
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE institutions
            SET approved = TRUE, approved_by = %s, approved_at = NOW()
            WHERE id = %s
        """, (current_user.id, institution_id))
        conn.commit()
        flash("Institution approved.", "success")
        # After approving institution and before redirect
        cur.execute("SELECT email FROM institutions WHERE id = %s;", (institution_id,))
        institution_email = cur.fetchone()
        if institution_email:
            msg = Message(
                "Charity Connect: Institution Approved",
                recipients=[institution_email[0]]
            )
            msg.body = (
                "Congratulations! Your institution has been approved and is now live on Charity Connect.\n\n"
                "You can now receive donations from our community.\n\n"
                "Best regards,\nCharity Connect Team"
            )
            mail.send(msg)
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error approving institution: {e}")
        flash("Error approving institution.", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'institution_admin')

        if not first_name or not last_name or not email or not password:
            flash("All fields are required.", "warning")
            return render_template('create_user.html')

        EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        if not re.match(EMAIL_REGEX, email):
            flash('Please enter a valid email address.', 'warning')
            return render_template('create_user.html')

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, password, role) VALUES (%s, %s, %s, %s, %s);",
                (first_name, last_name, email, hashed_password, role)
            )
            conn.commit()
            flash("User created successfully!", "success")
            return redirect(url_for('admin'))
        except Exception as e:
            if conn:
                conn.rollback()
            flash("Error creating user: " + str(e), "danger")
            return render_template('create_user.html')
        finally:
            cur.close()
            conn.close()
    return render_template('create_user.html')

@app.route('/admin/reset_password/<int:user_id>', methods=['GET', 'POST'])
@login_required
def reset_password(user_id):
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM users WHERE id = %s;", (user_id,))
    user = cur.fetchone()
    if not user:
        flash("User not found.", "danger")
        cur.close()
        conn.close()
        return redirect(url_for('admin'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password or not confirm_password:
            flash("Both password fields are required.", "warning")
            return render_template('reset_password.html', user=user)

        if not is_strong_password(new_password):
            flash('Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a digit, and a special character.', 'warning')
            return render_template('reset_password.html', user=user)

        if new_password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('reset_password.html', user=user)

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute("UPDATE users SET password = %s WHERE id = %s;", (hashed_password, user_id))
        conn.commit()
        flash("Password reset successfully!", "success")
        cur.close()
        conn.close()
        return redirect(url_for('admin'))

    cur.close()
    conn.close()
    return render_template('reset_password.html', user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
        conn.commit()
        flash("User deleted successfully.", "success")
    except Exception as e:
        if conn:
            conn.rollback()
        flash("Error deleting user: " + str(e), "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            flash("All fields are required.", "warning")
            return render_template('change_password.html')
        
        if not is_strong_password(new_password):
            flash('Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a digit, and a special character.', 'warning')
            return render_template('change_password.html')

        # Fetch current hashed password
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE id = %s;", (current_user.id,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user or not bcrypt.checkpw(old_password.encode('utf-8'), user[0].encode('utf-8')):
            flash("Old password is incorrect.", "danger")
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash("New passwords do not match.", "warning")
            return render_template('change_password.html')

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE users SET password = %s WHERE id = %s;", (hashed_password, current_user.id))
            conn.commit()
            flash("Password changed successfully!", "success")
            return redirect(url_for('admin'))
        except Exception as e:
            if conn:
                conn.rollback()
            flash("Error changing password: " + str(e), "danger")
        finally:
            cur.close()
            conn.close()
    return render_template('change_password.html')

@app.route('/admin/view_institution/<int:institution_id>')
@login_required
def view_institution(institution_id):
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT i.*, u.email AS submitted_by_email
        FROM institutions i
        LEFT JOIN users u ON i.user_id = u.id
        WHERE i.id = %s;
    """, (institution_id,))
    institution = cur.fetchone()

    # Fetch needed items for this institution
    cur.execute("""
        SELECT i.name FROM items i
        JOIN institution_needed_items ini ON i.id = ini.item_id
        WHERE ini.institution_id = %s;
    """, (institution_id,))
    needed_items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('view_institution.html', institution=institution, needed_items=needed_items)

@app.route('/admin/institutions')
@login_required
def admin_institutions():
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))
    institution_search = request.args.get('institution_search', '').strip()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if institution_search:
        cur.execute("""
            SELECT * FROM institutions
            WHERE name ILIKE %s OR email ILIKE %s
            ORDER BY approved DESC, name;
        """, (f'%{institution_search}%', f'%{institution_search}%'))
    else:
        cur.execute("SELECT * FROM institutions ORDER BY approved DESC, name;")
    institutions = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_institutions.html', institutions=institutions)

@app.route('/admin/suspend_institution/<int:institution_id>', methods=['POST'])
@login_required
def suspend_institution(institution_id):
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin_institutions'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE institutions SET suspended = TRUE WHERE id = %s;", (institution_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Institution suspended.", "success")
    return redirect(url_for('admin_institutions'))

@app.route('/admin/activate_institution/<int:institution_id>', methods=['POST'])
@login_required
def activate_institution(institution_id):
    institution_search = request.args.get('institution_search', '').strip()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if institution_search:
        cur.execute("""
            SELECT * FROM institutions
            WHERE name ILIKE %s OR email ILIKE %s
            ORDER BY approved DESC, name;
        """, (f'%{institution_search}%', f'%{institution_search}%'))
    else:
        cur.execute("SELECT * FROM institutions ORDER BY approved DESC, name;")
    institutions = cur.fetchall()
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin_institutions'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE institutions SET suspended = FALSE WHERE id = %s;", (institution_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Institution activated.", "success")
    return redirect(url_for('admin_institutions'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash("Please enter your email address.", "warning")
            return render_template('forgot_password.html')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
        user = cur.fetchone()
        if user:
            token = serializer.dumps(email, salt='password-reset')
            reset_url = url_for('reset_password_token', token=token, _external=True)
            msg = Message(
                "Charity Connect: Password Reset Request",
                recipients=[email]
            )
            msg.body = (
                f"To reset your password, click the link below:\n\n{reset_url}\n\n"
                "If you did not request a password reset, please ignore this email."
            )
            mail.send(msg)
        flash("If that email is registered, a password reset link has been sent.", "info")
        cur.close()
        conn.close()
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    try:
        email = serializer.loads(token, salt='password-reset', max_age=3600)
    except Exception:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not new_password or not confirm_password:
            flash("Both password fields are required.", "warning")
            return render_template('reset_password_token.html', token=token)
        if not is_strong_password(new_password):
            flash('Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a digit, and a special character.', 'warning')
            return render_template('reset_password_token.html', token=token)
        if new_password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('reset_password_token.html', token=token)
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = %s WHERE email = %s;", (hashed_password, email))
        conn.commit()
        cur.close()
        conn.close()
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for('login'))
    return render_template('reset_password_token.html', token=token)

@app.route('/institutions', methods=['GET'])
def institutions():
    conn = None
    cur = None
    institutions_list = []
    try:
        # Pagination setup
        page = int(request.args.get('page', 1))
        per_page = 5

        # Filters
        search = request.args.get('search', '').strip()
        location = request.args.get('location', '').strip()
        inst_type = request.args.get('type', '').strip()

        conn = get_db_connection()
        cur = conn.cursor()

        # For filter dropdowns
        cur.execute("SELECT DISTINCT location FROM institutions WHERE location IS NOT NULL AND location <> '' ORDER BY location;")
        locations = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT DISTINCT type FROM institutions WHERE type IS NOT NULL AND type <> '' ORDER BY type;")
        types = [row[0] for row in cur.fetchall()]

        # Build filter query
        filters = ["approved = TRUE", "(suspended IS NULL OR suspended = FALSE)"]
        params = []
        if search:
            filters.append("(name ILIKE %s OR email ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        if location:
            filters.append("location = %s")
            params.append(location)
        if inst_type:
            filters.append("type = %s")
            params.append(inst_type)
        where_clause = " AND ".join(filters)

        # Count total
        cur.execute(f"SELECT COUNT(*) FROM institutions WHERE {where_clause}", tuple(params))
        total = cur.fetchone()[0]
        total_pages = ceil(total / per_page)
        offset = (page - 1) * per_page

        # Fetch paginated institutions
        cur.execute(f"""
            SELECT * FROM institutions
            WHERE {where_clause}
            ORDER BY name
            LIMIT %s OFFSET %s
        """, (*params, per_page, offset))
        institutions_data = cur.fetchall()

        # For each institution, fetch their needed items
        for institution_row in institutions_data:
            institution_id = institution_row[0]
            cur.execute("""
                SELECT i.name
                FROM items i
                JOIN institution_needed_items ini ON i.id = ini.item_id
                WHERE ini.institution_id = %s;
            """, (institution_id,))
            needed_items = [row[0] for row in cur.fetchall()]

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
        total_pages = 1
        page = 1
        locations = []
        types = []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        'institutions.html',
        institutions=institutions_list,
        page=page,
        total_pages=total_pages,
        locations=locations,
        types=types
    )

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
            # Notify institution
            cur.execute("SELECT email, name FROM institutions WHERE id = %s;", (institution_id,))
            inst = cur.fetchone()
            if inst:
                msg = Message(
                    "Charity Connect: New Donation Received",
                    recipients=[inst['email']]
                )
                msg.body = (
                    f"Dear {inst['name']},\n\n"
                    f"You have received a new donation from {donor_name} ({donor_email}).\n"
                    "Please log in to your dashboard to view details and contact the donor to arrange delivery.\n\n"
                    "Best regards,\nCharity Connect Team"
                )
                mail.send(msg)

                msg = Message(
                "Charity Connect: Thank You for Your Donation",
                recipients=[donor_email]
                )
                msg.body = (
                    f"Dear {donor_name},\n\n"
                    "Thank you for your generous donation! The institution will contact you soon to arrange details.\n\n"
                    "Best regards,\nCharity Connect Team"
                )
                mail.send(msg)

            flash("Thank you for your donation! You will receive email an email shortly with further details!", "success")
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

@app.route('/mark_donation_received/<int:donation_id>', methods=['POST'])
@login_required
def mark_donation_received(donation_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Optionally, check if current_user is institution admin for this donation
        cur.execute("""
            UPDATE donations SET received = TRUE WHERE id = %s;
        """, (donation_id,))
        conn.commit()
        flash("Donation marked as received.", "success")
    except Exception as e:
        if conn:
            conn.rollback()
        flash("Error marking donation as received.", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('my_institution'))

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

        # Get donations for this institution
        cur.execute("""
            SELECT d.id, d.donor_name, d.donor_email, d.donation_type, d.donation_amount, d.item_quantity, 
                   i.name AS item_name, d.item_condition, d.service_description, d.donation_date, d.received
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
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not is_strong_password(password):
            flash('Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a digit, and a special character.', 'warning')
            return render_template('register.html', first_name=first_name, last_name=last_name, email=email)

        # Basic validation
        if not first_name or not last_name or not email or not password or not confirm_password:
            flash('All fields are required.', 'warning')
            return render_template('register.html', first_name=first_name, last_name=last_name, email=email)
        
        EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        
        # In your register route, after getting the email:
        if not re.match(EMAIL_REGEX, email):
            flash('Please enter a valid email address.', 'warning')
            return render_template('register.html', first_name=first_name, last_name=last_name, email=email)

        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return render_template('register.html', first_name=first_name, last_name=last_name, email=email)

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
                return render_template('register.html', first_name=first_name, last_name=last_name, email=email)

            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            # Insert new user into the database
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, password) VALUES (%s, %s, %s, %s);",
                (first_name, last_name, email, hashed_password.decode('utf-8'))
            )
            conn.commit()
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            user_id = cur.fetchone()[0]
            token = serializer.dumps(email, salt='email-confirm')
            confirm_url = url_for('confirm_email', token=token, _external=True)
            msg = Message(
                "Charity Connect: Confirm Your Email",
                recipients=[email]
            )
            msg.body = (
                f"Hi {first_name},\n\n"
                f"Thank you for registering! Please confirm your email by clicking the link below:\n\n"
                f"{confirm_url}\n\n"
                "If you did not register, please ignore this email.\n\n"
                "Best regards,\nCharity Connect Team"
            )
            mail.send(msg)
            flash('Registration successful! Please check your email to confirm your address.', 'success')
            return redirect(url_for('login'))

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"An error occurred during registration: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', first_name=first_name, last_name=last_name, email=email)

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # GET request: Display registration form
    return render_template('register.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)  # 1 hour expiry
    except Exception:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT confirmed FROM users WHERE email = %s;", (email,))
    user = cur.fetchone()
    if user and not user[0]:
        cur.execute("UPDATE users SET confirmed = TRUE WHERE email = %s;", (email,))
        conn.commit()
        flash('Your email has been confirmed! You can now log in.', 'success')
    else:
        flash('Account already confirmed or does not exist.', 'info')
    cur.close()
    conn.close()
    return redirect(url_for('login'))

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
            msg = Message(
                "Charity Connect: Institution Registration Received",
                recipients=[email]
            )
            msg.body = (
                f"Dear {name},\n\n"
                "Thank you for registering your institution with Charity Connect. "
                "Your submission has been received and is pending approval. "
                "We will notify you once your institution is approved.\n\n"
                "Best regards,\nCharity Connect Team"
            )
            mail.send(msg)
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

@app.route('/admin/donations')
@login_required
def admin_donations():
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))

    donation_search = request.args.get('donation_search', '').strip()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if donation_search:
        search_term = f"%{donation_search}%"
        cur.execute("""
            SELECT d.id, d.donor_name, d.donor_email, d.donation_type, d.donation_amount, d.item_quantity,
                   i.name AS item_name, d.item_condition, d.service_description, d.donation_date, d.received,
                   inst.name AS institution_name
            FROM donations d
            LEFT JOIN items i ON d.item_id = i.id
            LEFT JOIN institutions inst ON d.institution_id = inst.id
            WHERE d.donor_name ILIKE %s
               OR d.donor_email ILIKE %s
               OR inst.name ILIKE %s
            ORDER BY d.donation_date DESC;
        """, (search_term, search_term, search_term))
    else:
        cur.execute("""
            SELECT d.id, d.donor_name, d.donor_email, d.donation_type, d.donation_amount, d.item_quantity,
                   i.name AS item_name, d.item_condition, d.service_description, d.donation_date, d.received,
                   inst.name AS institution_name
            FROM donations d
            LEFT JOIN items i ON d.item_id = i.id
            LEFT JOIN institutions inst ON d.institution_id = inst.id
            ORDER BY d.donation_date DESC;
        """)
    donations = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_donations.html', donations=donations)

import csv
from io import StringIO
from flask import Response

@app.route('/admin/donations/export')
@login_required
def export_donations_csv():
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('admin'))

    donation_search = request.args.get('donation_search', '').strip()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if donation_search:
        search_term = f"%{donation_search}%"
        cur.execute("""
            SELECT d.donation_date, d.donor_name, d.donor_email, inst.name AS institution_name,
                   d.donation_type, d.donation_amount, d.item_quantity, i.name AS item_name,
                   d.item_condition, d.service_description, d.received
            FROM donations d
            LEFT JOIN items i ON d.item_id = i.id
            LEFT JOIN institutions inst ON d.institution_id = inst.id
            WHERE d.donor_name ILIKE %s
               OR d.donor_email ILIKE %s
               OR inst.name ILIKE %s
            ORDER BY d.donation_date DESC;
        """, (search_term, search_term, search_term))
    else:
        cur.execute("""
            SELECT d.donation_date, d.donor_name, d.donor_email, inst.name AS institution_name,
                   d.donation_type, d.donation_amount, d.item_quantity, i.name AS item_name,
                   d.item_condition, d.service_description, d.received
            FROM donations d
            LEFT JOIN items i ON d.item_id = i.id
            LEFT JOIN institutions inst ON d.institution_id = inst.id
            ORDER BY d.donation_date DESC;
        """)
    donations = cur.fetchall()
    cur.close()
    conn.close()

    # Prepare CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Date", "Donor", "Email", "Institution", "Type", "Amount", "Quantity", "Item",
        "Condition", "Service Description", "Received"
    ])
    for d in donations:
        cw.writerow([
            d['donation_date'].strftime('%Y-%m-%d') if d['donation_date'] else '',
            d['donor_name'],
            d['donor_email'],
            d['institution_name'],
            d['donation_type'],
            d['donation_amount'],
            d['item_quantity'],
            d['item_name'],
            d['item_condition'],
            d['service_description'],
            "Yes" if d['received'] else "No"
        ])
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=donations.csv"}
    )

from flask_mail import Message

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash("All fields are required.", "warning")
            return render_template('contact.html', name=name, email=email, message=message)

        # Send email to admin
        try:
            msg = Message(
                subject=f"Contact Us Message from {name}",
                sender=app.config.get('MAIL_DEFAULT_SENDER', email),
                recipients=[app.config.get('MAIL_USERNAME')],
                reply_to=email,
                body=f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
            )
            mail.send(msg)
            flash("Your message has been sent. Thank you!", "success")
            return redirect(url_for('contact'))
        except Exception as e:
            flash("Failed to send message. Please try again later.", "danger")
            print(e)
            return render_template('contact.html', name=name, email=email, message=message)

    return render_template('contact.html')

if __name__ == '__main__':
    app.run(debug=True)