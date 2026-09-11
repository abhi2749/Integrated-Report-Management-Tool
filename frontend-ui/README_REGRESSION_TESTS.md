# Frontend Regression Testing

This file documents the baseline manual smoke test for the current frontend.

No frontend source code is changed by Change #3.

## Manual smoke test

After starting the application:

1. Open the frontend.
2. Login with an existing test account.
3. Open Data Sources.
4. Verify an existing connection is visible.
5. Open Data Preview.
6. Verify an existing dataset can be selected.
7. Open Join Designer.
8. Verify the existing query/join UI loads.
9. Open Report Builder.
10. Verify an existing report can be opened or created.
11. Execute a small report.
12. Verify the result renders.
13. Verify an existing export workflow still opens.
14. Logout.
15. Login again.
16. Re-open the saved report.

Record any failure before changing application code.

## Rule

Change #3 adds the test foundation only. It does not refactor the frontend.
