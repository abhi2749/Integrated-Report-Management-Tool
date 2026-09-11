#!/usr/bin/env python3
"""
Generate isolated synthetic large-data sources for ReportingTool performance testing.

Nothing in this script reads company data. It only writes deterministic synthetic rows
to the dedicated stress-test MySQL/MongoDB containers.

Usage examples:
  python generate_stress_data.py --db mysql --rows 100000
  python generate_stress_data.py --db mysql --rows 1000000
  python generate_stress_data.py --db mongo --rows 1000000
"""

import argparse
import random
import time
from datetime import datetime, timedelta

MYSQL_CFG = {
    "host": "127.0.0.1", "port": 3307,
    "user": "stressuser", "password": "stress_password",
    "database": "stressdb",
}

MONGO_CFG = {
    "host": "127.0.0.1", "port": 27018,
    "username": "stressroot", "password": "stress_root_password",
    "authSource": "admin",
}

def synthetic_row(i: int):
    zones = ("NORTH", "SOUTH", "EAST", "WEST")
    circles = ("CIRCLE_A", "CIRCLE_B", "CIRCLE_C", "CIRCLE_D")
    base = datetime(2024, 1, 1)
    ts = base + timedelta(minutes=(i % 1000000))
    return (
        i + 1,
        f"MTR-{i + 1:09d}",
        zones[i % 4],
        circles[i % 4],
        f"DIV-{(i % 100) + 1:03d}",
        round(10 + ((i * 17) % 9000) / 100, 2),
        round(100 + ((i * 31) % 900000) / 100, 2),
        round(200 + ((i * 47) % 500000) / 100, 2),
        ts,
    )

def generate_mysql(rows: int, batch_size: int):
    try:
        import mysql.connector
    except ImportError:
        raise SystemExit("Install mysql-connector-python in the stress-test venv.")

    conn = mysql.connector.connect(**MYSQL_CFG)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS synthetic_meter_data (
            id BIGINT PRIMARY KEY,
            meter_id VARCHAR(32) NOT NULL,
            zone VARCHAR(16) NOT NULL,
            circle VARCHAR(32) NOT NULL,
            division VARCHAR(32) NOT NULL,
            load_kw DECIMAL(12,2) NOT NULL,
            energy_kwh DECIMAL(14,2) NOT NULL,
            voltage DECIMAL(12,2) NOT NULL,
            reading_time DATETIME NOT NULL,
            INDEX idx_zone (zone),
            INDEX idx_reading_time (reading_time)
        )
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM synthetic_meter_data")
    existing = cur.fetchone()[0]
    if existing >= rows:
        print(f"MySQL already has {existing:,} rows; requested {rows:,}. Nothing added.")
        cur.close(); conn.close()
        return

    insert_sql = """INSERT INTO synthetic_meter_data
        (id,meter_id,zone,circle,division,load_kw,energy_kwh,voltage,reading_time)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    start = existing
    started = time.time()
    for offset in range(start, rows, batch_size):
        end = min(offset + batch_size, rows)
        batch = [synthetic_row(i) for i in range(offset, end)]
        cur.executemany(insert_sql, batch)
        conn.commit()
        if end % (batch_size * 10) == 0 or end == rows:
            print(f"MySQL: {end:,}/{rows:,} rows ({time.time()-started:.1f}s)")
    cur.close(); conn.close()

def generate_mongo(rows: int, batch_size: int):
    try:
        from pymongo import MongoClient
    except ImportError:
        raise SystemExit("Install pymongo in the stress-test venv.")

    client = MongoClient(**MONGO_CFG)
    collection = client["stressdb"]["synthetic_meter_data"]
    existing = collection.estimated_document_count()
    if existing >= rows:
        print(f"MongoDB already has about {existing:,} documents; requested {rows:,}. Nothing added.")
        return

    started = time.time()
    for offset in range(existing, rows, batch_size):
        end = min(offset + batch_size, rows)
        docs = []
        for i in range(offset, end):
            r = synthetic_row(i)
            docs.append({
                "_id": r[0],
                "meter_id": r[1],
                "zone": r[2],
                "circle": r[3],
                "division": r[4],
                "load_kw": r[5],
                "energy_kwh": r[6],
                "voltage": r[7],
                "reading_time": r[8],
            })
        collection.insert_many(docs, ordered=False)
        if end % (batch_size * 10) == 0 or end == rows:
            print(f"MongoDB: {end:,}/{rows:,} documents ({time.time()-started:.1f}s)")
    collection.create_index("zone")
    collection.create_index("reading_time")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", choices=("mysql", "mongo"), required=True)
    p.add_argument("--rows", type=int, choices=(100000, 1000000, 5000000, 10000000), required=True)
    p.add_argument("--batch-size", type=int, default=5000)
    args = p.parse_args()
    if args.db == "mysql":
        generate_mysql(args.rows, args.batch_size)
    else:
        generate_mongo(args.rows, args.batch_size)

if __name__ == "__main__":
    main()
