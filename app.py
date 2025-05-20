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
        institutions_list = cur.fetchall()

    except (psycopg2.Error, Exception) as e:
        print(f"Error fetching institutions: {e}")
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

            # Insert needed items
            item_ids = []
            if needed_items:
                 item_names = needed_items
                 if 'other' in item_names and other_item_spec:
                     item_names.remove('other')

                 if item_names:
                     cur.execute("SELECT id FROM items WHERE name = ANY(%s);", (item_names,))
                     item_ids = [row[0] for row in cur.fetchall()]

            for item_id in item_ids:
                cur.execute(
                    "INSERT INTO institution_items (institution_id, item_id) VALUES (%s, %s);",
                    (institution_id, item_id)
                )

            conn.commit()

            flash("Institution registered successfully!") # Add flash message
            return redirect(url_for('institutions'))

        except (psycopg2.Error, Exception) as e:
            if conn:
                conn.rollback()
            print(f"An error occurred during registration: {e}")
            # You might want to flash an error message here as well
            flash("An error occurred during registration. Please try again.")
            return redirect(url_for('institutions')) # Redirect back even on error
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

if __name__ == '__main__':
    app.run(debug=True)