# main.py
from flask import Flask, flash, json, render_template, request, redirect, jsonify, url_for, session
from pymongo import MongoClient
import os

import requests

app = Flask(__name__)
secret_key = os.urandom(24)
app.secret_key = secret_key

# MongoDB configuration
MONGO_URI = 'mongodb://localhost:27017/'
DB_NAME = 'yellow'
COLLECTION_NAME = 'loginDetails'

GOOGLE_PLACES_API_KEY = ''

@app.route('/')
def home_redirect():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        latitude = request.form['latitude']
        longitude = request.form['longitude']

        if check_credentials(username, password):
            session['username'] = username
            session['latitude'] = latitude
            session['longitude'] = longitude

            add_location_to_past_locations(username, latitude, longitude)
            return redirect(url_for('user_home'))  
        else:
            flash("Invalid credentials")  
            return redirect('/login')  

    return render_template('login.html')

@app.route('/user_home')
def user_home():
    # Check if the user is logged in (username exists in the session)
    if 'username' in session: 
        return render_template('home.html', username=session['username'], latitude = session['latitude'], longitude=session['longitude'])
    else:
        return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/new_user', methods=['GET', 'POST'])
def new_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        latitude = request.form['latitude']
        longitude = request.form['longitude']

        if username_exists(username):
            flash("Username already exists. Please choose a different username.")
            return redirect('/login')

        session['username'] = username
        session['latitude'] = latitude
        session['longitude'] = longitude
        store_new_user(username, password, latitude, longitude)

        return redirect(url_for('user_home')) 

    return render_template('new_user.html')

def username_exists(username):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    existing_user = collection.find_one({"username": username})
    return existing_user is not None

def store_new_user(username, password, latitude, longitude):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    new_user = {
        "username": username,
        "password": password,
        "current_location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "past_locations": [{
            "latitude": latitude,
            "longitude": longitude
        }]
    }

    collection.insert_one(new_user)

def check_credentials(username, password):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    user = collection.find_one({"username": username, "password": password})
    if user:
        return True
    else:
        return False

def add_location_to_past_locations(username, latitude, longitude):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    user = collection.find_one({"username": username})

    if user:
        location_exists = any(
            int(float(entry["latitude"])) == int(float(latitude)) and int(float(entry["longitude"])) == int(float(longitude))
            for entry in user["past_locations"]
            if entry["latitude"] is not None and entry["longitude"] is not None
        )
        if not location_exists:
            new_location = {
                "latitude": latitude,
                "longitude": longitude
            }
            
            collection.update_one({"username": username}, {"$push": {"past_locations": new_location}})

@app.route('/view_past_locations')
def view_past_locations():
    past_locations = get_past_locations_from_db(session['username'])
    past_locations_json = json.dumps(past_locations)

    return render_template('view_past_locations.html', past_locations_json=past_locations_json)

def get_past_locations_from_db(username):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    user = collection.find_one({"username": username})

    if user and 'past_locations' in user:
        return user['past_locations']
    else:
        return []

@app.route('/restaurants')
def restaurants_nearby():

    latitude = session['latitude']
    longitude = session['longitude']

    if latitude is None or longitude is None:
        return "Error: Latitude and longitude not found in session."

    restaurants = fetch_restaurants(latitude, longitude)
    return render_template('restaurants.html', restaurants=restaurants)

def fetch_restaurants(latitude, longitude):
    #FourSquare Call to Get NearBy Restaurants
    url = "https://api.foursquare.com/v3/places/search"

    params = {
        "query": "restaurant",
        "ll": f'{latitude},{longitude}',
        "open_now": "true",
        "sort":"DISTANCE",
        "limit":50
    }

    #Add FourSquare API Key in Authorization
    headers = {
        "Accept": "application/json",
        "Authorization": ""
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        restaurants = data["results"]

        new_resto = []
        for result in restaurants:
            restaurant_name = ""
            for cat in result['categories']:
                restaurant_name = cat['name']
            restaurant_address = result['location']['formatted_address']
            restaurant_latitude = result['geocodes']['main']['latitude']
            restaurant_longitude = result['geocodes']['main']['longitude']
            new_resto.append({
                "name": restaurant_name,
                "address": restaurant_address,
                "latitude": restaurant_latitude,
                "longitude": restaurant_longitude
            })

        return new_resto
    else:
        print(f"Request failed with status code: {response.status_code}")
        return []
    
if __name__ == '__main__':
    app.run(debug=True)
