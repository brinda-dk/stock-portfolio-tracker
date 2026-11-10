# Stock Portfolio Tracker and Analyzer

A college mini project using Flask, MySQL, HTML, CSS, Bootstrap, and JavaScript.

## Features

- Secure registration, login, session authentication, and logout
- Stock Explorer with validated stock creation
- User-scoped watchlists
- Buy and sell transactions with weighted-average cost basis
- Oversell protection and transaction rollback
- Holdings, realized P/L, and historical-price-based unrealized P/L
- Historical OHLCV price browsing with date filters
- CSV historical-price import with validation and atomic writes
- SMA20/SMA50 historical indicators and portfolio analytics
- Royal midnight navy, champagne-gold, and warm ivory responsive UI
- CSRF protection for state-changing forms

## Project structure

```text
app.py
database/schema.sql
services/
  analytics_service.py
  database.py
  stock_service.py
  transaction_service.py
  user_service.py
templates/
static/css/style.css
static/js/script.js
tests/
requirements.txt
.env.example
```

## Setup in the VS Code terminal

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally:

```text
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=stock_portfolio
SECRET_KEY=use-a-long-random-secret
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=0
```

Never commit `.env`. It is excluded by `.gitignore`.

Use `SESSION_COOKIE_SECURE=1` when serving the application over HTTPS. Keep
`FLASK_DEBUG=0` outside local development; the application defaults to debug
off so Werkzeug's debugger is not exposed accidentally.

## Create the MySQL schema

Make sure MySQL Server is running and `mysql` is available on PATH:

```powershell
Get-Content .\database\schema.sql | mysql --host=localhost --user=root --password
```

Enter the password only at the prompt. The schema uses `CREATE TABLE IF NOT EXISTS`
and does not delete existing rows.

Verify the tables:

```powershell
mysql --host=localhost --user=root --password --database=stock_portfolio -e "SHOW TABLES;"
```

Expected tables:

```text
historical_prices
stocks
transactions
users
watchlists
```

## Verify the database connection

```powershell
python -m flask --app app test-db
```

Expected output:

```text
MySQL connection successful.
```

Connection errors show a safe message and never print the password.

## Run the application

```powershell
python app.py
```

Open <http://127.0.0.1:5000>.

Private pages require login:

- `/dashboard`
- `/stocks`
- `/watchlist`
- `/transactions`
- `/historical-prices`
- `/analytics`

## Historical-price CSV import

Use this exact header row:

```text
stock_id,price_date,open_price,high_price,low_price,close_price,volume
```

Dates must use `YYYY-MM-DD`. Prices and volume must be non-negative. The importer
rejects malformed rows, invalid stock IDs, duplicate rows, and existing
`(stock_id, price_date)` records. A failed import is rolled back.

SMA20 and SMA50 are calculated only when enough valid observations exist. They
describe historical prices and are not predictions. Current portfolio value and
unrealized P/L remain unavailable until reliable historical closing prices exist
for every held position; purchase prices are never treated as market prices.

## Run tests

```powershell
python -m pytest
```

The tests use mocks and isolated fixtures; they do not delete project data.

Syntax check:

```powershell
python -m py_compile app.py services\analytics_service.py services\database.py services\user_service.py services\stock_service.py services\transaction_service.py
```

## Manual smoke test

1. Register a new account and log in.
2. Add a stock from **Stocks**.
3. Add a buy transaction and verify it appears in history and holdings.
4. Sell part of the holding; attempt to oversell and confirm it is rejected.
5. Add historical-price CSV rows and open **History**.
6. Apply a date filter and confirm the chart uses only recorded rows.
7. Open **Analytics** and confirm unavailable prices are shown as unavailable.
8. Log out and confirm private URLs redirect to `/login`.
