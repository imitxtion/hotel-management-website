# Hotel Management System

A simple web application built with Python (Flask) and MySQL for managing basic hotel operations, including rooms, customers, cleaners, check-ins/outs, and invoicing.

## Description

This application provides a web interface for a hotel administrator to manage:
* Hotel room inventory and status.
* Customer information and stays (check-in/check-out).
* Employee (cleaner) details.
* Cleaning schedules for different floors.
* Running queries for specific operational data.
* Generating invoices for completed stays.
* Viewing a basic hotel status and income report.

## Features

* **Dashboard:** Overview of room availability.
* **Room Management:** View all rooms, types, costs, floor, and occupancy status.
* **Customer Management:**
    * Check-in (Settle) new customers, assigning them to available rooms.
    * View currently checked-in guests.
    * View history of all customers (past and present).
    * Check-out (Evict) customers.
* **Employee Management:**
    * Hire new employees (cleaners).
    * View list of current employees.
    * Dismiss employees (also removes their schedule).
* **Schedule Management:**
    * Assign employees to clean specific floors on specific days of the week.
    * View the complete cleaning schedule.
    * Delete schedule entries.
* **Queries & Reports:**
    * Find occupants currently in a specific room.
    * Find current guests who arrived from a specific city.
    * Find which employee is scheduled to clean the floor of a specific guest's room on a given day.
    * View overall hotel report (current room status, total income from completed stays).
* **Invoicing:** Automatically generate a printable invoice upon customer check-out.

## Technology Stack

* **Backend:** Python 3
* **Framework:** Flask
* **Database:** MySQL
* **DB Connector:** `mysql-connector-python`
* **Frontend:** HTML5, CSS3
* **CSS Framework:** Bootstrap 5
* **Templating:** Jinja2
* **Environment Variables:** `python-dotenv`

## Setup and Installation

1.  **Prerequisites:**
    * Python 3.x installed.
    * MySQL Server installed and running.
    * Git (optional, for cloning).

2.  **Clone Repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

3.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    # Activate (Linux/macOS)
    source venv/bin/activate
    # Activate (Windows)
    venv\Scripts\activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Database Setup:**
    * Connect to your MySQL server (e.g., using MySQL Workbench or command line).
    * Create the database:
        ```sql
        CREATE DATABASE hotel_management_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        USE hotel_management_system;
        ```
    * Execute the table creation SQL commands found in the initial setup instructions or potentially provided in a `.sql` file (if added). This includes creating `room_types`, `rooms`, `customers`, `employees`, `cleaning_schedule` tables.
    * *Optional:* Insert sample data (room types, rooms, employees) for easier testing.

6.  **Configure Environment Variables:**
    * Create a file named `.env` in the project root directory.
    * Add your configuration details:
        ```dotenv
        DB_HOST=localhost
        DB_USER=your_mysql_username
        DB_PASSWORD=your_mysql_password
        DB_NAME=hotel_management_system
        FLASK_SECRET_KEY=your_very_secret_random_string_here # IMPORTANT: Change this!
        ```
    * Replace placeholders with your actual MySQL credentials and choose a secure secret key.

7.  **Run the Application:**
    ```bash
    flask run
    ```
    The application will typically be available at `http://127.0.0.1:5000`.

## Database Schema

The application uses the following main tables:

* `room_types`: Stores room categories (single, double, triple) and their cost per day.
* `rooms`: Represents individual hotel rooms, linking to `room_types`, storing floor number, room number, and occupancy status.
* `customers`: Stores customer details (passport, name, city), check-in/out dates, and the assigned room (`assigned_room_id` FK to `rooms`).
* `employees`: Stores employee (cleaner) details.
* `cleaning_schedule`: Links employees to floors they clean on specific days of the week (`employee_id` FK to `employees`).

## Usage

Access the application via your web browser. The navigation bar provides access to all major sections: Dashboard, Rooms, Customers (Current, Check-in, History), Employees (View, Hire), Cleaning Schedule, Queries & Reports, and the Hotel Overview Report. Administrative actions like check-out, dismiss employee, delete schedule are available as buttons within the relevant tables.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
