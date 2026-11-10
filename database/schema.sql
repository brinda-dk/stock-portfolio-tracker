CREATE DATABASE IF NOT EXISTS stock_portfolio;

USE stock_portfolio;

CREATE TABLE IF NOT EXISTS users (
    user_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stocks (
    stock_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    exchange_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    stock_id INT UNSIGNED NOT NULL,
    transaction_type ENUM('BUY', 'SELL') NOT NULL,
    quantity DECIMAL(18, 6) NOT NULL,
    price_per_share DECIMAL(18, 6) NOT NULL,
    transaction_date DATE NOT NULL,
    CONSTRAINT chk_transactions_quantity CHECK (quantity > 0),
    CONSTRAINT chk_transactions_price CHECK (price_per_share >= 0),
    CONSTRAINT fk_transactions_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_transactions_stock
        FOREIGN KEY (stock_id) REFERENCES stocks (stock_id) ON DELETE RESTRICT,
    INDEX idx_transactions_user_date (user_id, transaction_date),
    INDEX idx_transactions_stock_date (stock_id, transaction_date)
);

CREATE TABLE IF NOT EXISTS watchlists (
    watchlist_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    stock_id INT UNSIGNED NOT NULL,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_watchlists_user_stock UNIQUE (user_id, stock_id),
    CONSTRAINT fk_watchlists_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_watchlists_stock
        FOREIGN KEY (stock_id) REFERENCES stocks (stock_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS historical_prices (
    price_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    stock_id INT UNSIGNED NOT NULL,
    price_date DATE NOT NULL,
    open_price DECIMAL(18, 6) NOT NULL,
    high_price DECIMAL(18, 6) NOT NULL,
    low_price DECIMAL(18, 6) NOT NULL,
    close_price DECIMAL(18, 6) NOT NULL,
    volume BIGINT UNSIGNED NOT NULL,
    CONSTRAINT uq_historical_prices_stock_date UNIQUE (stock_id, price_date),
    CONSTRAINT chk_historical_prices_open CHECK (open_price >= 0),
    CONSTRAINT chk_historical_prices_high CHECK (high_price >= 0),
    CONSTRAINT chk_historical_prices_low CHECK (low_price >= 0),
    CONSTRAINT chk_historical_prices_close CHECK (close_price >= 0),
    CONSTRAINT fk_historical_prices_stock
        FOREIGN KEY (stock_id) REFERENCES stocks (stock_id) ON DELETE CASCADE,
    INDEX idx_historical_prices_date (price_date)
);
