from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages # Import flash and get_flashed_messages
import psycopg2
import os 

def create_app():
    app = Flask(__name__)
    return app

app = Flask(__name__)
app.secret_key = 'mwambui' # Add a secret key for sessions
# Database Configuration
DATABASE_URL = "postgresql://postgres:r2d2c3po@localhost:5432/dhub"
# Function to get a database connection
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

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
        institutions_data = cur.fetchall() # Fetch institution data

        # For each institution, fetch their needed items
        for institution_row in institutions_data:
            institution_id = institution_row[0] # Get the institution id
            cur.execute("""
                SELECT i.name
                FROM items i
                JOIN institution_items ii ON i.id = ii.item_id
                WHERE ii.institution_id = %s;
            """, (institution_id,))
            needed_items = [row[0] for row in cur.fetchall()] # Fetch all items for this institution

            # Create a dictionary or list to hold institution data and its items
            # We'll use a dictionary for easier access in the template
            institution_dict = {
                'id': institution_row[0],
                'name': institution_row[1],
                'location': institution_row[2],
                'email': institution_row[3],
                'phone': institution_row[4],
                'website': institution_row[5],
                'type': institution_row[6],
                'photo_filename': institution_row[7],
                'needed_items': needed_items # Add the list of needed items
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

@app.route('/institutions', methods=['POST'])
def register_institution():
    conn = None
    cur = None
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            name = request.form['name']
            email = request.form['email']
            phone = request.form['phone']
            location = request.form['location']
            institution_type = request.form['type']
            website = request.form.get('website')
            needed_items = request.form.getlist('needed_items')
            other_item_spec = request.form.get('other_item_spec')

            photo = request.files.get('photo')
            photo_filename = None
            if photo and photo.filename:
                upload_folder = 'static/uploads'
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                photo_filename = photo.filename # Still using simple filename, consider secure_filename for production
                photo_path = os.path.join(upload_folder, photo_filename)
                photo.save(photo_path)

            # Insert institution data
            cur.execute(
                "INSERT INTO institutions (name, email, phone, location, type, website, photo_filename) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;",
                (name, email, phone, location, institution_type, website, photo_filename)
            )
            institution_id = cur.fetchone()[0]

            # Insert needed items and handle "Other"
            item_ids = []
            if needed_items:
                 item_names = needed_items
                 if 'other' in item_names and other_item_spec:
                     # If 'other' is selected and specification is provided,
                     # remove 'other' and add the specified item to item_names
                     item_names.remove('other')
                     item_names.append(other_item_spec) # Add the specified item name

                 if item_names:
                     # Check if the item exists in the 'items' table or insert it
                     processed_item_ids = []
                     for item_name in item_names:
                         cur.execute("SELECT id FROM items WHERE name = %s;", (item_name,))
                         item_row = cur.fetchone()
                         if item_row:
                             processed_item_ids.append(item_row[0])
                         else:
                             # If item doesn't exist, insert it and get its ID
                             cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id;", (item_name,))
                             processed_item_ids.append(cur.fetchone()[0])

                     # Insert into institution_items
                     for item_id in processed_item_ids:
                         cur.execute(
                             "INSERT INTO institution_items (institution_id, item_id) VALUES (%s, %s);",
                             (institution_id, item_id)
                         )

            conn.commit()

            flash("Institution registered successfully!")
            return redirect(url_for('institutions'))

        except (psycopg2.Error, Exception) as e:
            if conn:
                conn.rollback()
            print(f"An error occurred during registration: {e}")
            flash("An error occurred during registration. Please try again.")
            return redirect(url_for('institutions'))
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

@app.route('/donate/<int:institution_id>', methods=['GET', 'POST'])
def donate(institution_id):
    conn = None
    cur = None
    institution = None
    items = [] # To store the list of available items

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- GET Request ---
        if request.method == 'GET':
            # Fetch institution details
            cur.execute("SELECT id, name FROM institutions WHERE id = %s;", (institution_id,))
            institution_data = cur.fetchone()
            if institution_data:
                institution = {'id': institution_data[0], 'name': institution_data[1]}
            else:
                # Handle case where institution is not found
                flash("Institution not found.", "danger")
                return redirect(url_for('institutions'))

            # Fetch all available donation items from the 'items' table, excluding non-donatable types
            cur.execute("SELECT id, name FROM items WHERE name NOT IN ('Cash', 'Service') ORDER BY name;")
            items_data = cur.fetchall()
            items = [{'id': row[0], 'name': row[1]} for row in items_data]

            return render_template('donate.html', institution=institution, items=items)

        # --- POST Request ---
        elif request.method == 'POST':
            # Get form data
            donor_name = request.form['donor_name']
            donor_email = request.form.get('donor_email')
            donor_phone = request.form.get('donor_phone')
            donor_type = request.form['donor_type']
            donation_type = request.form['donation_type']
            message = request.form.get('message')

            # *** Add server-side validation for mandatory fields ***
            if not donor_email:
                flash("Email is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))

            if not donor_phone:
                flash("Phone number is required.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))
            # *** End of new validation ***

            donation_amount = None
            item_id = None
            item_quantity = None
            item_condition = None
            service_description = None

            # Validate and get data based on donation type (existing code)
            if donation_type == 'cash':
                # ... (cash validation) ...
                donation_amount = request.form.get('donation_amount')
                if not donation_amount or float(donation_amount) <= 0:
                     flash("Please enter a valid donation amount.", "warning")
                     return redirect(url_for('donate', institution_id=institution_id))
                donation_amount = float(donation_amount)


            elif donation_type == 'item':
                # ... (item validation) ...
                item_id = request.form.get('item_id')
                item_quantity = request.form.get('item_quantity')
                item_condition = request.form.get('item_condition')

                if not item_id or not item_quantity or int(item_quantity) <= 0:
                    flash("Please select an item and enter a valid quantity.", "warning")
                    return redirect(url_for('donate', institution_id=institution_id))
                item_id = int(item_id)
                item_quantity = int(item_quantity)

            elif donation_type == 'service':
                # ... (service validation) ...
                service_description = request.form.get('service_description')
                if not service_description or not service_description.strip():
                     flash("Please provide a description of the service.", "warning")
                     return redirect(url_for('donate', institution_id=institution_id))


            else:
                # Handle invalid donation type
                flash("Invalid donation type selected.", "warning")
                return redirect(url_for('donate', institution_id=institution_id))


            # Insert donation record into the donations table (existing code)
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
    
if __name__ == '__main__':
    app.run(debug=True)