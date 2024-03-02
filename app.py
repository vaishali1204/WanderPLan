from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import pandas as pd
from bson import ObjectId
from urllib.parse import quote_plus
from datetime import datetime
import json

import json

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder

app.secret_key = 'wanderplan'

# Replace 'your_username' and 'your_password' with your MongoDB Atlas cluster username and password
escaped_username = quote_plus('utkarshbhardwaj45')
escaped_password = quote_plus('thapar@2023')

# Update your connection string with the appropriate SSL options
connection_string = f'mongodb+srv://{escaped_username}:{escaped_password}@cluster0.bd3jn01.mongodb.net/'

# Connect to MongoDB
client = MongoClient(connection_string)

db = client.WanderPlan

# Function for generating itinerary
def generate_itinerary(location, total_budget, total_days):
    # Clear the previous budget and tasks data for the current itinerary
    db.budget.delete_many({'itinerary_id': session.get('itinerary_id')})
    db.tasks.delete_many({'itinerary_id': session.get('itinerary_id')})
    
    # Load attractions data from attractions.csv
    attractions_df = pd.read_csv('attractions_temp.csv')

    # Filter attractions for the specified location
    location_attractions = attractions_df[attractions_df['location'] == location]

    # Sort attractions by rating in descending order
    location_attractions = location_attractions.sort_values(by='rating', ascending=False)

    # Calculate the number of attractions to visit each day
    attractions_per_day = len(location_attractions) // total_days
    remaining_attractions = len(location_attractions) % total_days

    # Initialize variables to track total spending and total hours spent
    total_spending = 0
    total_hours_spent = 0

    # Initialize the list to store days in the itinerary
    itinerary_days = []

    # Loop through each day
    for day in range(1, total_days + 1):
        # Initialize variables for the day
        daily_budget = total_budget / total_days
        daily_hours_limit = 12
        daily_spending = 0
        daily_hours_spent = 0
        selected_attractions = set()

        # Initialize the list to store attractions for the current day
        day_attractions = []

        # Determine the number of attractions to visit on the current day
        attractions_to_visit = attractions_per_day + (1 if day <= remaining_attractions else 0)

        # Loop until the daily budget is reached or all attractions are visited
        for _ in range(attractions_to_visit):
            # Select the next attraction
            attraction = location_attractions.iloc[0]

            # Check if the attraction has already been selected
            if attraction['attraction'] not in selected_attractions:
                # Check if the time spent on the attraction fits within the daily time limit
                if daily_hours_spent + attraction['time'] <= daily_hours_limit:
                    # Convert NumPy int64 to native Python int
                    attraction_data = {
                        'name': attraction['attraction'],
                        'rating': float(attraction['rating']),
                        'price': float(attraction['price']),
                        'time': float(attraction['time'])
                    }

                    # Add the attraction to the list for the current day
                    day_attractions.append(attraction_data)

                    # Update variables
                    selected_attractions.add(attraction['attraction'])
                    daily_spending += float(attraction['price'])
                    total_spending += float(attraction['price'])
                    daily_hours_spent += float(attraction['time'])
                    total_hours_spent += float(attraction['time'])

            # Remove the selected attraction from the list
            location_attractions = location_attractions.iloc[1:]

        # Add data for the current day to the list of days
        itinerary_days.append({
            'attractions': day_attractions,
            'daily_spending': daily_spending,
            'daily_hours_spent': daily_hours_spent
        })

    # Display total spending and total hours spent for the trip
    print("\nTotal Summary:")
    print(f"Total Spent for the entire trip: {total_spending} INR (out of {total_budget} INR)")
    print(f"Total Hours Spent for the entire trip: {total_hours_spent} hours")

    # Return the generated itinerary without '_id'
    return {
        '_id': str(ObjectId()),
        'location': location,
        'total_budget': total_budget,
        'total_days': total_days,
        'days': itinerary_days,
        'total_spending': total_spending,
        'total_hours_spent': total_hours_spent
    }

@app.route('/')
def index():
    return render_template('index.html')

def store_itinerary(itinerary_data):
    # Remove the '_id' field from the itinerary data
    itinerary_data['_id'] = str(itinerary_data.get('_id'))

    # Clear all entries in the 'budget' collection
    db.budget.delete_many({})

    # Clear all entries in the 'tasks' collection
    db.tasks.delete_many({})

    # Store the generated itinerary in MongoDB
    db.itineraries.insert_one(itinerary_data)

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary_route():
    if request.method == 'POST':
        location = request.form['location']
        total_budget = float(request.form['budget'])
        total_days = int(request.form['days'])

        #Generate itinerary
        itinerary = generate_itinerary(location, total_budget, total_days)

        # Store the generated itinerary in the session
        session['itinerary'] = itinerary

        session['itinerary_id'] = itinerary['_id']  # Store the itinerary ID in the session

        # Store the generated itinerary in MongoDB
        store_itinerary(itinerary)

        # Redirect to the plan_trip route
        return redirect(url_for('plan_trip'))

@app.route('/plan_trip', methods=['GET', 'POST'])
def plan_trip():
    # Retrieve itinerary from the session
    itinerary = session.get('itinerary', None)

    if request.method == 'POST':
        if 'member' in request.form and 'expense' in request.form:
            # Budget Management
            member = request.form['member']
            expense_amount = float(request.form['expense'])
            add_expense(member, expense_amount)

        if 'task' in request.form:
            # Task Planner
            task = request.form['task']
            add_task(task)

    # Retrieve budget and tasks data from MongoDB
    budget_data = get_budget_data()
    tasks_data = get_tasks_data()

    print("Itinerary data:", itinerary)

    return render_template('plan_trip.html', itinerary=itinerary, budget_data=budget_data, tasks_data=tasks_data)

def add_expense(member, amount):
    # Add an expense to MongoDB
    db.budget.insert_one({'member': member, 'amount': amount, 'date': datetime.now()})

def add_task(task):
    # Add a task to MongoDB
    db.tasks.insert_one({'task': task})

def get_budget_data():
    # Retrieve budget data from MongoDB
    budget_data = list(db.budget.find())
    return budget_data

def get_tasks_data():
    # Retrieve tasks data from MongoDB
    tasks_data = list(db.tasks.find())
    return tasks_data

if __name__ == '__main__':
    app.run(debug=True)

