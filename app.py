import os
from flask import Flask, render_template, session, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize the Flask application
app = Flask(__name__)

# Configure the SQLite database
# On Vercel, the filesystem is read-only except for /tmp.
if os.environ.get('VERCEL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/ecommerce.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Secret key is needed for session management (used in later steps for the cart)
app.config['SECRET_KEY'] = 'beginner-ecommerce-secret-key'

# Initialize the Flask-SQLAlchemy extension to manage our database
db = SQLAlchemy(app)

# Define the User database model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Define the Product database model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Product {self.name}>'

# Route for the Home Page (Storefront View)
@app.route('/')
def index():
    # Fetch all products from the database using SQLAlchemy
    products = Product.query.all()
    # Render index.html and pass the list of products to the template
    return render_template('index.html', products=products)

# Route for User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for('register'))
            
        # Check if username is already taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username is already taken. Please choose another.")
            return redirect(url_for('register'))
            
        # Create user and encrypt password using SHA256 hashing
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))
        
    return render_template('register.html')

# Route for User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # Save user session details
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f"Welcome back, {user.username}!")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.")
            return redirect(url_for('login'))
            
    return render_template('login.html')

# Route for User Logout
@app.route('/logout')
def logout():
    # Remove user session keys
    session.pop('user_id', None)
    session.pop('username', None)
    flash("You have been logged out.")
    return redirect(url_for('index'))

# Route to Add a Product to the Cart
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    
    if 'cart' not in session:
        session['cart'] = {}
        
    cart = session['cart']
    product_id_str = str(product_id)
    cart[product_id_str] = cart.get(product_id_str, 0) + 1
    session['cart'] = cart
    
    flash(f"Added '{product.name}' to your cart!")
    # Redirect back to where user came from, or storefront home page
    return redirect(request.referrer or url_for('index'))

# Route to Decrement/Remove an Item from the Cart
@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'cart' in session:
        cart = session['cart']
        product_id_str = str(product_id)
        if product_id_str in cart:
            if cart[product_id_str] > 1:
                cart[product_id_str] -= 1
                flash("Decremented item quantity.")
            else:
                cart.pop(product_id_str)
                flash("Removed item from cart.")
            session['cart'] = cart
    return redirect(request.referrer or url_for('cart'))

# Route to Instantly Delete an Item from the Cart
@app.route('/delete_from_cart/<int:product_id>')
def delete_from_cart(product_id):
    if 'cart' in session:
        cart = session['cart']
        product_id_str = str(product_id)
        if product_id_str in cart:
            cart.pop(product_id_str)
            session['cart'] = cart
            flash("Removed item from cart.")
    return redirect(request.referrer or url_for('cart'))

# Route to View the Shopping Cart
@app.route('/cart')
def cart():
    cart_session = session.get('cart', {})
    cart_items = []
    total_price = 0.0
    
    for product_id_str, quantity in cart_session.items():
        product = Product.query.get(int(product_id_str))
        if product:
            item_total = product.price * quantity
            total_price += item_total
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'total': item_total
            })
            
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

# Route for One-Click Checkout
@app.route('/checkout')
def checkout():
    # Restrict checkout to authenticated users
    if 'user_id' not in session:
        flash("Please log in to complete your checkout.")
        return redirect(url_for('login'))
        
    session.pop('cart', None)
    flash("Order Placed Successfully!")
    return redirect(url_for('index'))

# Route for AI Agent Availability Chat
@app.route('/api/chat', methods=['POST'])
def ai_chat():
    data = request.get_json() or {}
    message = data.get('message', '').strip().lower()
    
    if not message:
        return jsonify({
            'thought': 'The user sent an empty message. I will ask them to type a vehicle name.',
            'tool': 'None',
            'observation': 'No text provided.',
            'response': 'Hello! I am the Big Boy Toyz AI Sales Assistant. Please type a vehicle name to check its availability.'
        })
        
    # Analyze message keywords to decide actions
    thought = f"The user is asking: '{data.get('message')}'. I need to parse this query to find keywords related to our luxury fleet."
    
    # Simple keyword mappings
    keywords_roadster = ['roadster', 'apex', 'convertible', 'electric roadster']
    keywords_supercar = ['supercar', 'veloce', 'v12', 'lambo']
    keywords_cruiser = ['cruiser', 'grand cruiser', 'gt', 'v8', 'sedan']
    keywords_porsche = ['porsche', '911', 'gt3', 'flat-six']
    keywords_bmw = ['bmw', 'm5', 'competition', 'beemer', 'xdrive']
    
    matched_car = None
    if any(k in message for k in keywords_roadster):
        matched_car = "Apex Roadster"
    elif any(k in message for k in keywords_supercar):
        matched_car = "Veloce Supercar"
    elif any(k in message for k in keywords_cruiser):
        matched_car = "Grand Cruiser GT"
    elif any(k in message for k in keywords_porsche):
        matched_car = "Porsche 911 GT3"
    elif any(k in message for k in keywords_bmw):
        matched_car = "BMW M5 Competition"
        
    if matched_car:
        tool = f"database_query(name='{matched_car}')"
        # Search the database using SQLAlchemy
        product = Product.query.filter_by(name=matched_car).first()
        if product:
            observation = f"Found database match: {product.name} priced at ${product.price:,.2f}."
            response = f"Yes! The **{product.name}** is currently in stock in our showroom. It is priced at **${product.price:,.2f}**. {product.description} Would you like to add it to your cart?"
        else:
            observation = f"Database query returned no records for name='{matched_car}'."
            response = f"I found references to the {matched_car}, but it doesn't appear to be in our database right now. Let me know if you want to see our alternative models!"
    else:
        # User asked a generic question, scan database
        tool = "database_query_all()"
        all_products = Product.query.all()
        car_names = [p.name for p in all_products]
        observation = f"Scanned fleet. Found {len(car_names)} vehicles: {', '.join(car_names)}."
        
        # Build general response listing available cars
        car_list_str = ", ".join([f"**{p.name}** (${p.price:,.2f})" for p in all_products])
        response = f"I couldn't identify the specific car you are looking for. However, our current showroom catalog features: {car_list_str}. What vehicle would you like to inspect?"
        
    return jsonify({
        'thought': thought,
        'tool': tool,
        'observation': observation,
        'response': response
    })

# Helper function to initialize the database and load seed data
def init_db():
    with app.app_context():
        # Create database tables for Product and User models
        db.create_all()

        # Migrate existing photography database to cars if necessary
        first_product = Product.query.first()
        if first_product and first_product.name == "Classic Camera":
            print("Old photography seed data detected. Clearing product table...")
            Product.query.delete()
            db.session.commit()

        # Add sample data if the product table is empty
        if Product.query.count() == 0:
            print("Populating database with sample sports and luxury cars...")
            sample_products = [
                Product(
                    name="Apex Roadster",
                    description="A sleek, high-performance electric convertible with lightning acceleration and a futuristic carbon fiber cabin.",
                    price=185000.00,
                    image_url="https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800&q=80"
                ),
                Product(
                    name="Veloce Supercar",
                    description="Precision track handling meets raw carbon fiber engineering. Powered by a naturally aspirated 6.5L V12 engine.",
                    price=320000.00,
                    image_url="https://images.unsplash.com/photo-1544829099-b9a0c07fad1a?w=800&q=80"
                ),
                Product(
                    name="Grand Cruiser GT",
                    description="A twin-turbo V8 grand tourer offering supreme luxury, semi-autonomous driving, and effortless high-speed comfort.",
                    price=145000.00,
                    image_url="https://images.unsplash.com/photo-1563720223185-11003d516935?w=800&q=80"
                ),
                Product(
                    name="Porsche 911 GT3",
                    description="A naturally aspirated track weapon designed for pure driver engagement. High-revving flat-six engine and signature rear wing.",
                    price=225000.00,
                    image_url="https://images.unsplash.com/photo-1614162692292-7ac56d7f7f1e?w=800&q=80"
                ),
                Product(
                    name="BMW M5 Competition",
                    description="The ultimate executive performance sedan. Powered by a 4.4L twin-turbo V8 producing 617 HP, paired with an M xDrive AWD system.",
                    price=115000.00,
                    image_url="https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=800&q=80"
                )
            ]
            db.session.bulk_save_objects(sample_products)
            db.session.commit()
            print("Database products populated successfully!")

        # Ensure 'Porsche 911 GT3' exists in the database for existing setups
        porsche_exists = Product.query.filter_by(name="Porsche 911 GT3").first()
        if not porsche_exists:
            print("Seeding Porsche 911 GT3 for existing database...")
            porsche_car = Product(
                name="Porsche 911 GT3",
                description="A naturally aspirated track weapon designed for pure driver engagement. High-revving flat-six engine and signature rear wing.",
                price=225000.00,
                image_url="https://images.unsplash.com/photo-1614162692292-7ac56d7f7f1e?w=800&q=80"
            )
            db.session.add(porsche_car)
            db.session.commit()
            print("Porsche 911 GT3 seeded successfully!")

        # Ensure 'BMW M5 Competition' exists in the database for existing setups
        bmw_exists = Product.query.filter_by(name="BMW M5 Competition").first()
        if not bmw_exists:
            print("Seeding BMW M5 Competition for existing database...")
            bmw_car = Product(
                name="BMW M5 Competition",
                description="The ultimate executive performance sedan. Powered by a 4.4L twin-turbo V8 producing 617 HP, paired with an M xDrive AWD system.",
                price=115000.00,
                image_url="https://images.unsplash.com/photo-1617814076367-b759c7d7e738?w=800&q=80"
            )
            db.session.add(bmw_car)
            db.session.commit()
            print("BMW M5 Competition seeded successfully!")

        # Ensure the 'driver' user account exists
        driver_user = User.query.filter_by(username="driver").first()
        if not driver_user:
            print("Creating default seed user 'driver'...")
            seed_user = User(username="driver")
            seed_user.set_password("drive123")
            db.session.add(seed_user)
            db.session.commit()
            print("Default seed user 'driver' created successfully!")

# Initialize database at the module level to ensure compatibility with Vercel serverless imports
init_db()

# Run the local development server when the file is run directly
if __name__ == '__main__':
    print("Starting Flask development server...")
    app.run(debug=True)
