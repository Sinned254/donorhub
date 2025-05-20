from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages # Import flash and get_flashed_messages
import psycopg2
import os 

def create_app():
    app = Flask(__name__)
    return app

app = Flask(__name__)
app.secret_key = 'mwambui' # Add a secret key for sessions
# Database Configuration (Replace with your actual database credentials)
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

            # ... (rest of your form data retrieval and photo upload logic) ...
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


@app.route('/donate/<int:institution_id>')
def donate(institution_id):
    # This is a placeholder for the donate page
    # You will implement the donation logic here later
    return f"This is the donate page for institution with ID: {institution_id}"


if __name__ == '__main__':
    app.run(debug=True)