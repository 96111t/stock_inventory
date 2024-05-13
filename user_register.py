import bcrypt
import json

USERS_FILE = 'documents/users.json'

def read_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def register_user(username, password):
    users = read_data(USERS_FILE)  # Load existing users
    hashed_password = hash_password(password)  # Hash the password

    # Check if the username already exists
    if username in users:
        return "Username already exists"

    # Add the new user with the hashed password
    users[username] = hashed_password.decode('utf-8')  # Store the hashed password as a string

    # Write the updated users back to the file
    with open(USERS_FILE, 'w') as file:
        json.dump(users, file, indent=4)

    return "User registered successfully"

print("----- User Registration -----")
username = input("Enter username: ")
password = input("Enter password: ")

print(register_user(username, password))