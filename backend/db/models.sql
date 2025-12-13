-- STORES
CREATE TABLE IF NOT EXISTS stores (
    store_id INT PRIMARY KEY,
    store_name VARCHAR(100),
    region VARCHAR(50),
    city VARCHAR(50),
    open_date DATE
);

-- PRODUCTS
CREATE TABLE IF NOT EXISTS products (
    product_id INT PRIMARY KEY,
    sku VARCHAR(50),
    product_name VARCHAR(150),
    category VARCHAR(50),
    subcategory VARCHAR(50),
    cost_price DECIMAL(10,2),
    selling_price DECIMAL(10,2)
);

-- CUSTOMERS
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(150),
    gender VARCHAR(10),
    age INT,
    city VARCHAR(50)
);

-- SALES TRANSACTIONS
CREATE TABLE IF NOT EXISTS sales_transactions (
    txn_id BIGINT PRIMARY KEY,
    store_id INT,
    product_id INT,
    customer_id INT,
    txn_timestamp DATETIME,
    quantity INT,
    total_amount DECIMAL(10,2),
    payment_method VARCHAR(20),
    FOREIGN KEY (store_id) REFERENCES stores(store_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- INVENTORY SNAPSHOTS
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    store_id INT,
    product_id INT,
    snapshot_date DATE,
    on_hand_qty INT,
    on_order_qty INT,
    FOREIGN KEY (store_id) REFERENCES stores(store_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- INCIDENTS
CREATE TABLE IF NOT EXISTS incidents (
    incident_id BIGINT PRIMARY KEY,
    store_id INT,
    created_at DATETIME,
    resolved_at DATETIME,
    incident_type VARCHAR(50),
    severity VARCHAR(10),
    description TEXT,
    resolution_note TEXT,
    status VARCHAR(20),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

-- ALERTS
CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    store_id INT,
    created_at DATETIME,
    alert_type VARCHAR(50),
    details TEXT,
    is_resolved BOOLEAN DEFAULT FALSE
);
