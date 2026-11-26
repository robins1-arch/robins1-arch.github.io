# MYP Multiplication & Division Arena — hosted classroom edition

This is a deployable game and account server, not a live hosted website. Do not open index.html directly: the account system requires server.py. The general mathematics V4 game is unchanged. Use a separate database and deployment for this edition.

## Run a private test on your computer

Install Python 3.10 or newer. Extract the ZIP. Open a terminal in this directory. Choose your own strong class enrolment code and teacher password. On macOS/Linux:

```sh
export ARENA_JOIN_CODE='replace-with-a-long-random-class-code'
export ARENA_TEACHER_PASSWORD='replace-with-a-unique-long-teacher-password'
python3 server.py
```

On Windows PowerShell:

```powershell
$env:ARENA_JOIN_CODE = 'replace-with-a-long-random-class-code'
$env:ARENA_TEACHER_PASSWORD = 'replace-with-a-unique-long-teacher-password'
py server.py
```

Visit http://127.0.0.1:8000 on that computer. Students choose **New scholar? Create account** and enter a nickname, unique handle, password (minimum 8 characters) and the class code. Teacher: sign in with handle `teacher` and the teacher password. Students may start at Iron I or take the optional one-time placement diagnostic (maximum Gold I). They need a new account in this separate edition. The teacher sees the private class dashboard. Sign out after using a shared device. The server saves progress after each change; wait for **Cloud saved** before closing the game. If a second device changes the save, the old device cannot overwrite it; use Reload cloud save.

## Deploy for multiple devices

Use an organisation-approved server with a persistent volume for SQLite. Put it behind an HTTPS reverse proxy; do not expose the Python development HTTP service directly to the Internet. Set the two secrets as deployment environment variables, set `ARENA_HTTPS=1` (secure cookies), and set `ARENA_DB` to a file on the persistent volume (e.g. `/data/multiplicative.sqlite3`). Start `python server.py --host 0.0.0.0 --port 8000` behind the proxy. The provided Dockerfile is optional; mount `/data`, use HTTPS at the proxy and provide your secrets as environment variables. Share the HTTPS URL with authorised students only. Keep the same class code and persistent database across restarts. Configure backups using SQLite's online backup API, not merely copying a live WAL database file. School IT must approve the hosting region, retention and student privacy arrangements before actual use. Use pseudonyms and avoid personal details.

## Included

- `index.html`: complete game, including the 50-tier multiplication and division curriculum, existing visual assets, diagnostic, mastery, account and teacher interfaces.
- `server.py`: account and save API with SQLite, separate session cookie, scrypt password hashing, enrolment code, access controls and revision checks.
- `Dockerfile`: optional deployment packaging.
- `multiplicative_bank.js`: readable source of the question generators embedded in the HTML. Editing it alone does not change the game; the shipped HTML is the runnable version.
- `test_v4.py`, `test_hosted.py`: integration tests using Python Playwright and Chromium, run against a temporary test database. Do not run against a real class. Set ARENA_TEST_URL, ARENA_JOIN_CODE=testclass123 and ARENA_TEACHER_PASSWORD=teacher-test-123 for the test instance only.

## Changes from general mathematics V4

This is a separate curriculum. All numerical questions target multiplication, division or an application of multiplicative reasoning. Addition/subtraction may occur as supporting steps in distributive multiplication, remainders, percentage changes and index laws, not as standalone topics. Advanced applications include fractions, ratios, rates, geometry, proportionality, powers, scientific notation and multiplicative growth and decay. These are an MYP-inspired practice sequence, not an official IB syllabus or a full MYP assessment instrument.

The optional diagnostic contains ten questions per prerequisite block (two per topic: one multiplication/scaling and one division/inverse), requires at least eight correct and at least one correct per topic, and cannot place a student above Gold I (tier 16). No diagnostic coins. Placement credit is not earned mastery; skipped topics return in retrieval practice. A student can complete a tier only through independent practice and its checkpoint. Using the single method hint gives feedback but no coins and no advancement; another independent question follows. Hints persist across devices and are disabled in promotion gates and independent repair tasks. Accuracy is tracked separately for the primary multiplication/scaling and division/inverse operations; conceptual checkpoints are recorded in topic/criterion analytics instead. Mixed-operation problems are classified by their primary operation.

Four numerical forms per tier (200 tier-form slots, not all structurally unique across neighbouring topics), plus topic-specific method checks and ten additional pattern/application reasoning generators. Question selection rotates forms and searches against saved question fingerprints across all tiers. The finite pool, bounded history (800 fingerprints per tier) and bounded search mean exact repeats may eventually occur, particularly for early arithmetic. A different context or parameter does not automatically constitute a different mathematical skill. The game targets recognition and application, not a full independent assessment of MYP criteria B/C/D.

## Validation and limits

A local SQLite server plus independent Chromium browser sessions passed registration, login, two-device save restoration, assisted-answer non-advancement and zero coins, diagnostic resumption, four starting ranks, balanced diagnostic operations, class rankings, teacher access, stale-save conflict protection and sign-out. 40,000 sampled numerical instances were checked for finite expected answers, answer-parser consistency and diversity (32,679 distinct instances summed across the 200 tier/form samples, not a globally deduplicated count). 1,000 additional reasoning instances passed distinct-option checks. A 282-task simulated full progression completed at Tier 50 with zero exact question fingerprint repetitions across tiers; final completion reward could not be repeated. The simulation used the generated expected answers, so these tests do not independently prove every mathematical answer. Real-world iPad/Safari and HTTPS testing remain outstanding.

No live hosting URL has been provisioned. The original V4 database and this edition are intentionally incompatible: the same rank in different curricula is not comparable. The server rejects old curriculum saves and refuses to initialise against a database containing another edition's progress. Use a fresh database. Do not overwrite V4's files or database. This is a practice game, not a tamper-proof assessment: questions and scoring remain client-side. It is not a security audit. Use school-approved hosting and student pseudonyms. Password recovery and multi-class administration remain future work.
