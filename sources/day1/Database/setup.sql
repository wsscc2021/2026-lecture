CREATE DATABASE IF NOT EXISTS isolation_demo;
USE isolation_demo;

CREATE TABLE IF NOT EXISTS accounts (
    id      INT PRIMARY KEY,
    name    VARCHAR(50),
    balance INT
);

CREATE TABLE IF NOT EXISTS orders (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT,
    amount     INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_amount (amount)
);

-- 초기 데이터
INSERT INTO accounts VALUES (1, 'Alice', 1000), (2, 'Bob', 500);
INSERT INTO orders (id, user_id, amount) VALUES (1, 1, 50), (2, 1, 100), (3, 1, 200);
