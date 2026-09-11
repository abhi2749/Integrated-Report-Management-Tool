# ReportingTool A10 Large-Data Stress Test

This environment is isolated from C:\ReportingTool and from company databases.

## Start synthetic databases

From this folder:

    docker compose up -d

Check:

    docker compose ps

MySQL is exposed on localhost:3307.
MongoDB is exposed on localhost:27018.

## Install generator dependencies

Use a separate virtual environment if desired:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

## Generate data

Start with 100K:

    python generate_stress_data.py --db mysql --rows 100000
    python generate_stress_data.py --db mongo --rows 100000

Then increase the same source:

    python generate_stress_data.py --db mysql --rows 1000000
    python generate_stress_data.py --db mysql --rows 5000000
    python generate_stress_data.py --db mysql --rows 10000000

The same commands can be used for MongoDB.

The generator is append-only up to the requested target and never reads company data.

## Verify counts

MySQL:

    docker exec -it reportingtool-stress-mysql mysql -ustressuser -pstress_password -D stressdb -e "SELECT COUNT(*) AS total_rows FROM synthetic_meter_data;"

MongoDB:

    docker exec -it reportingtool-stress-mongo mongosh --quiet --username stressroot --password stress_root_password --authenticationDatabase admin --eval "db=db.getSiblingDB('stressdb'); print(db.synthetic_meter_data.countDocuments());"

## Important

Do not connect the stress database to production/company systems.

After the first 100K baseline, we will connect this isolated source to ReportingTool and measure FE + BE execution, pagination, dashboard aggregation, and full export.

The source remains intact. We will not add an artificial 100/1000/5000-row source limit to make the application appear fast.

## Backend engine stress harness

The isolated `run_backend_engine_stress.py` script exercises the actual
ReportingTool backend JOIN engine and SQLite ResultStore without connecting to
MySQL, MongoDB, ClickHouse, or company data.

From `C:\ReportingTool`:

    python stress-test\run_backend_engine_stress.py

The default is 100,000 rows per JOIN side and a 1 MB spill threshold. Increase
progressively after the baseline succeeds:

    python stress-test\run_backend_engine_stress.py --rows 500000 --spill-memory-mb 1
    python stress-test\run_backend_engine_stress.py --rows 1000000 --spill-memory-mb 4

The harness validates exact JOIN row count/checksum, measures elapsed time and
Python allocation peak, validates ResultStore ingestion/pagination, and cleans
up its temporary files automatically.

This is a stress benchmark, not part of the normal `backend/tests` suite.


STEP 8D v2 WINDOWS FIX
----------------------
If the original stress harness reports:

    PermissionError: [WinError 32] ... results.sqlite3

use this v2 harness. The test itself passed the JOIN but Windows retained
the SQLite file handle briefly during TemporaryDirectory cleanup.

v2 explicitly releases the ResultStore reference, runs garbage collection,
and retries temporary-directory cleanup with a short backoff on Windows.

Placement:
    C:\ReportingTool\stress-test\run_backend_engine_stress.py

Run:
    python stress-test\run_backend_engine_stress.py

Then:
    python stress-test\run_backend_engine_stress.py --rows 500000 --spill-memory-mb 1
