from flask import (Flask, request, jsonify, render_template, flash, redirect,
                   url_for, session, send_file, Response)
import json
import csv
from io import StringIO
from functools import wraps
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red, black


def load_secret_key():
    with open('documents/secret_key.bin', 'rb') as f:
        return f.read()

app = Flask(__name__)

# Instead of setting the secret_key directly in the file, we now use an environment variable
app.secret_key = load_secret_key()


# Path to your JSON file
DATA_FILE = 'inventory.json'
USERS_FILE = 'users.json'

def read_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def is_logged_in():
    return 'username' in session

def write_data(data):
    for category in data:
        data[category] = sorted(data[category], key=lambda x: x['name'])
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def log_user_activity(username, action):
    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {username} {action}\n"
    with open('user_activity_log.txt', 'r+') as log_file:
        current_contents = log_file.read()
        log_file.seek(0)  # Move to the start of the file
        log_file.write(log_entry + current_contents)  # Prepend the new log entry

@app.route('/')
def index():
    # if not is_logged_in():
    #     flash('Please log in to access this page.', 'warning')
    #     # return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/main')  # This is the new route for the main page
@login_required
def main():
    if not is_logged_in():
        # flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    username = session['username'].capitalize()  # Capitalize the username
    return render_template('index.html', username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = read_data(USERS_FILE)
        username = request.form['username']
        password = request.form['password']

        if username in users and users[username] == password:
            session['username'] = username
            log_user_activity(username, 'logged in')  # Log the login activity
            return redirect(url_for('main'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')  # Handle cases where the username might not be in the session
    session.pop('username', None)
    log_user_activity(username, 'logged out')  # Log the logout activity
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

def record_change(data, category, product_id, new_quantity):
    """Record the quantity with datetime."""
    for product in data[category]:
        if product['id'] == product_id:
            if 'changes' not in product:
                product['changes'] = []
            product['changes'].append({
                'quantity_history': new_quantity,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            product['quantity'] = new_quantity  # Update the quantity
            break

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        data = read_data(DATA_FILE)
        product = request.form
        category = product['category']
        product_id = product['id'].strip()
        product_name = product['name'].strip()  # Trim whitespace

        # Validate the provided ID for uniqueness
        for existing_category, products in data.items():
            for existing_product in products:
                if existing_product['id'] == product_id:
                    flash('Product ID already exists. Please use a unique ID.', 'error')
                    return redirect(url_for('add_product'))

        # Check if the category exists and if the product name is unique within the category
        if category not in data:
            data[category] = []
        else:
            # Check for duplicate product names within the category
            for existing_product in data[category]:
                if existing_product['name'].lower() == product_name.lower():
                    flash('Product name already exists in this category.', 'error')
                    return redirect(url_for('add_product'))

        new_product = {
            'id': product_id,
            'name': product_name,
            'quantity': int(product['quantity']),
            'optimum_quantity': int(product['optimum_quantity']),
            'changes': [{
                'quantity_change': int(product['quantity']),
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }]
        }
        data[category].append(new_product)
        write_data(data)
        flash('Product added successfully!')
        return redirect(url_for('add_product'))
    return render_template('add_product.html')


@app.route('/stock_take', methods=['GET', 'POST'])
@login_required
def stock_take():
    if request.method == 'POST':
        data = read_data(DATA_FILE)
        updates = request.get_json()  # Change here to handle JSON data
        category = updates['category']
        product_id = updates['id']
        new_quantity = int(updates['quantity'])
        record_change(data, category, product_id, new_quantity)
        write_data(data)
        return jsonify({'message': 'Stock updated successfully!'}), 200
    return render_template('stock_take.html')

@app.route('/export_order_form', methods=['GET'])
def export_order_form():
    file_type = request.args.get('type', 'pdf')  # Default to PDF if no type is specified
    data = read_data(DATA_FILE)
    filename = f"order_form_{datetime.now().strftime('%Y-%m-%d')}"

    if file_type.lower() == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['product_id', 'quantity'])

        for category, products in data.items():
            for product in products:
                order_number = product['optimum_quantity'] - product['quantity']
                if order_number > 0:
                    writer.writerow([product['id'], abs(order_number)])

        output.seek(0)
        filename += '.csv'
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}"})
    else:
        filename += '.pdf'
        c = canvas.Canvas(filename, pagesize=letter)
        c.setFont("Helvetica", 12)
        y_position = 750  # Starting Y position, top of the page
        line_height = 20

        # Print titles
        c.drawString(72, y_position, "Category")
        c.drawString(172, y_position, "Name")
        c.drawString(472, y_position, "Amount to Order")
        y_position -= line_height

        previous_category = None
        for category, products in sorted(data.items()):
            for product in products:
                order_number = product['optimum_quantity'] - product['quantity']
                if order_number > 0:
                    if category != previous_category:
                        if previous_category is not None:  # Avoid drawing a line before the first category
                            y_position -= line_height // 2  # Add some space before the line
                            c.line(72, y_position, 550, y_position)  # Draw the line
                            y_position -= line_height // 2  # Add some space after the line
                        previous_category = category
                    c.setFillColor(black)
                    c.drawString(72, y_position, category)
                    c.drawString(172, y_position, product['name'])
                    c.setFillColor(red)
                    c.drawString(472, y_position, str(order_number))
                    y_position -= line_height
                    if y_position < 50:  # Check if we are at the end of the page
                        c.showPage()  # Create a new page
                        y_position = 750  # Reset the Y position
                        c.setFont("Helvetica", 12)  # Reset the font
                        # Reprint titles for new page
                        c.setFillColor(black)
                        c.drawString(72, y_position, "Category")
                        c.drawString(172, y_position, "Name")
                        c.drawString(472, y_position, "Amount to Order")
                        y_position -= line_height

        c.save()
        return send_file(filename, as_attachment=True)

@app.route('/api/products', methods=['GET'])
def get_products_by_category():
    category = request.args.get('category', '')
    data = read_data(DATA_FILE)
    if category:
        filtered_products = data.get(category, [])
    else:
        # If no category is specified, return all products
        filtered_products = []
        for products in data.values():
            filtered_products.extend(products)
    return jsonify(filtered_products)

@app.route('/api/product_history', methods=['GET'])
def product_history():
    product_id = request.args.get('id')
    data = read_data(DATA_FILE)
    for category, products in data.items():
        for product in products:
            if product['id'] == product_id:
                # Return the changes history for the matched product
                return jsonify(product.get('changes', []))
    return jsonify({'error': 'Product not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)