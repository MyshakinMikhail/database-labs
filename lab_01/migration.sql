CREATE TABLE statuses (
    id INT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE order_statuses_history (
    id INT PRIMARY KEY,
    order_id INT NOT NULL,
    status_id INT NOT NULL,
    time TIMESTAMP NOT NULL
);

-- open, closed, cancelled
INSERT INTO statuses (id, name)
VALUES (1, 'open'), (2, 'closed'), (3, 'cancelled');
INSERT INTO order_statuses (id, status_id, order_id, history)
SELECT id, status, order_id, 'open'
FROM orders;

