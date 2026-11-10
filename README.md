# Stock Portfolio Tracker and Analyzer

A college mini project built with Python Flask, MySQL, HTML, CSS, Bootstrap, and JavaScript.

## Current milestone

This milestone adds the MySQL schema, environment-based connection module,
password hashing helpers, database connection test, and user authentication.
Stock transaction features will be added later.

The schema creates `users`, `stocks`, `transactions`, `watchlists`, and
`historical_prices` with primary keys, foreign keys, unique constraints, and
validation checks. It uses `CREATE TABLE IF NOT EXISTS`, so rerunning it does
not delete existing rows.

## Project structure

```text
stock-portfolio-tracker/
├── app.py                  # Flask application and homepage route
├── requirements.txt        # Python packages
├── .env.example            # Safe configuration template
├── database/
│   └── schema.sql          # MySQL database setup
├── services/
│   ├── __init__.py         # Service-layer package
│   ├── database.py         # Reusable MySQL connection helpers
│   └── user_service.py     # Password hashing and parameterized user queries
├── templates/
│   └── index.html          # Homepage
├── static/
│   ├── css/style.css       # Application styles
│   └── js/script.js        # Browser-side JavaScript
└── tests/
    ├── test_app.py         # Homepage test
    └── test_database.py    # Password and SQL-safety tests
```

## Setup in VS Code

Open the project folder in VS Code, then run these commands in the integrated terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `.env` with `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and a long
random `SECRET_KEY`. The secret signs Flask login sessions and must not be
committed. MySQL uses port `3306` by default. `.env` is ignored by Git.

## Create the MySQL database from the VS Code terminal

MySQL Server must be installed and running first. The `mysql` command must be available on PATH.

From the project root, run:

```powershell
Get-Content .\database\schema.sql | mysql -h localhost -P 3306 -u root -p
```

Enter your MySQL password when prompted. This command creates the `stock_portfolio` database and all project tables. It does not require MySQL Workbench.

Then test the application connection:

```powershell
python -m flask --app app test-db
```

Success prints:

```text
MySQL connection successful.
```

If it fails, check that MySQL Server is running and that the four `DB_*` values in `.env` match your MySQL installation. The command reports a clear configuration/availability error without exposing the password.

To execute the schema from the VS Code integrated PowerShell terminal, replace
`localhost` and `root` with the `DB_HOST` and `DB_USER` values from your local
`.env` file. Enter the password only when prompted:

```powershell
Get-Content .\database\schema.sql | mysql --host=localhost --user=root --password
```

To verify every table was created:

```powershell
mysql --host=localhost --user=root --password --database=stock_portfolio -e "SHOW TABLES;"
```

The output must include:

```text
historical_prices
stocks
transactions
users
watchlists
```

## Test registration and login

Start the application:

```powershell
python app.py
```

Open these URLs in a browser:

1. `http://127.0.0.1:5000/register` — enter a name, email, password, and matching confirmation.
2. `http://127.0.0.1:5000/login` — use the registered email and password.
3. Successful login redirects to `/dashboard`.
4. Select **Logout**, then open `/dashboard` again. It should redirect to `/login`.

Passwords are hashed with Werkzeug before being sent to MySQL. Registration
uses parameterized SQL, and the database unique constraint prevents duplicate
emails.

## Run the application

```powershell
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000 in a browser.

## Run the test

```powershell
.\.venv\Scripts\python.exe -m pytest
```
