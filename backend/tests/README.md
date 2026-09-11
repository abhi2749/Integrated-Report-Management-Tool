# Reporting Tool Regression Tests

## Purpose

This test folder is a safety net for the existing working baseline.

The first test set intentionally avoids:
- real database connections
- changes to application data
- migrations
- starting a production server
- changing authentication behavior

It is designed to catch accidental breakage after code changes.

## Run

From the `backend` directory:

```powershell
python -m pytest tests -q
```

If `pytest` is not installed:

```powershell
python -m pip install pytest
```

## What is covered initially

- Password hashing does not return plaintext.
- Correct passwords verify successfully.
- Incorrect passwords are rejected.
- Password hashing uses a different salt for repeated hashes.
- Core backend modules remain importable.
- Query engine modules remain importable.

## Important

These are baseline regression tests, not the final V1 test suite.

Do not interpret a green result here as proof that:
- MySQL connectivity works,
- MongoDB connectivity works,
- ClickHouse connectivity works,
- cross-database JOINs work,
- reports execute correctly,
- exports work,
- frontend behavior is correct.

Those require dedicated integration tests later.

## Test philosophy

Every future modification should ideally follow:

1. Run the existing tests.
2. Make one isolated change.
3. Run the tests again.
4. Manually smoke-test the affected UI/API flow.
5. Only then move to the next change.
