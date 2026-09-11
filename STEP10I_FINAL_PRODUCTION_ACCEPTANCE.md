# Step 10I — Final Production Acceptance

Step 10I is the final acceptance gate for Step 10. It validates the complete
10A→10I chain across Backend, Frontend, and deployment contracts.

## Acceptance sequence

1. Run the complete Backend test suite.
2. Run the complete Frontend test suite.
3. Run Frontend lint and production build.
4. Build Backend and Frontend Docker images without cache.
5. Start the Compose stack.
6. Verify Backend `/health` and `/ready`.
7. Verify both services remain running/healthy after startup.
8. Exercise a representative execution → result page → export lifecycle.
9. Verify cancellation and failed-job handling.
10. Verify persistent job/key stores survive application restart.
11. Verify no `.env`, local virtual environment, cache, or runtime data is sent in Docker build contexts.
12. Record PASS/FAIL for Backend, Frontend, BE↔FE integration, and deployment.

## Automated checks added by 10I

Backend:

```powershell
cd C:\ReportingTool\backend
python -m pytest tests/test_step10i_final_acceptance.py -q
```

Frontend:

```powershell
cd C:\ReportingTool\frontend-ui
npm test
npm run lint
npm run build
```

## Docker acceptance

```powershell
docker compose down

docker compose build --no-cache backend frontend

docker compose up -d

docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

10I does not introduce artificial row/file limits. Existing format-specific
limits remain output-format constraints, not reporting-engine dataset limits.

**Step 10 ends at 10I. No 10J/10K is defined.**
