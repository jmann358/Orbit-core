PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE missions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    title      TEXT NOT NULL,
    outcome    TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
INSERT INTO missions VALUES(1,'jason','P0-1 verification: installed Luna egress and memory posture','A verdict, proven from the installed source and config on THRONE, on whether Luna can silently send chat or approved memory to any cloud provider — recorded as a mission receipt.','closed','2026-10-14T01:40:21+00:00','2026-10-14T01:43:05+00:00');
INSERT INTO missions VALUES(2,'jason','Fix PR #66''s SQLite defect (hurdle 1: unreliable verification)','PR #66''s optional verifier can no longer abort the worker: a database error during verification leaves the completed job result intact, proven by a new regression test and the PR suite passing locally.','closed','2026-10-14T01:51:05+00:00','2026-10-14T02:05:58+00:00');
INSERT INTO missions VALUES(3,'jason','First live provider dispatch through the broker (P1-CREDIT proof)','Luna v2 routes a real prompt to a free provider, returns the answer, and accounts every token in the resource ledger - /bin/bash spent.','closed','2026-10-14T02:21:18+00:00','2026-10-14T02:21:43+00:00');
INSERT INTO missions VALUES(4,'jason','Scout''s first job — what Orbit-core says it is, and where its own records disagree','A source-cited digest from Luna''s Research Scout, verified by Rowan against the sources, closed with a receipt','closed','2026-10-14T02:36:47+00:00','2026-10-14T02:37:18+00:00');
INSERT INTO missions VALUES(5,'jason','Daily team health routine','Scheduled run of routine ''daily-team-health'' (daily); created by scheduler tick at 2026-10-14T03:11:39+00:00.','closed','2026-10-14T03:11:39+00:00','2026-10-14T03:11:52+00:00');
INSERT INTO missions VALUES(6,'jason','Builder''s first live draft','','closed','2026-10-14T03:25:17+00:00','2026-10-14T03:25:32+00:00');
CREATE TABLE steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    owner       TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    description TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('routine', 'consequential')),
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'done', 'skipped')),
    result      TEXT NOT NULL DEFAULT '',
    evidence    TEXT NOT NULL DEFAULT '',
    UNIQUE (mission_id, seq)
);
INSERT INTO steps VALUES(1,1,'jason',1,'Inspect the launcher (start_luna_agent.py) for model-endpoint forcing and API-key/cloud stripping','routine','done','','Launcher read in full (211 lines): binds 127.0.0.1:8000 only; --self-build forces LUNA_MODEL_URL=http://127.0.0.1:11434/v1 and pops LUNA_API_KEY and LUNA_AGENT_ALLOW_CLOUD from env; LUNA_CLOUD_MODE=1 makes it refuse to start; readiness reports cloud_deployed=False, remote_access=False.');
INSERT INTO steps VALUES(2,1,'jason',2,'Inspect the launchd plist and service environment for endpoints, keys, and cloud flags','routine','done','','com.orbit.luna.plist read: live env contains only LUNA_DB_PATH (local sqlite), LUNA_SERVICE_MODE=1, PATH, PYTHONUNBUFFERED — no API keys, no cloud endpoints, no cloud flags.');
INSERT INTO steps VALUES(3,1,'jason',3,'Inspect cloud_worker.py and core.py for outbound calls to non-local hosts','routine','done','','scripts/cloud_worker.py + luna/cloud_worker.py read and grepped: despite the name, the worker is a local SQLite job queue (cloud_jobs table) with zero network calls; handlers allowlisted (heartbeat, project_health, development_draft). Latent path: draft-PR publishing needs LUNA_GITHUB_PR_AUTO_ENABLED=1 — not set in the live env.');
INSERT INTO steps VALUES(4,1,'jason',4,'Confirm chat and memory storage is local-only (database path, no cloud memory configured)','routine','done','','core.py + developer_model.py grepped and read: cloud chat exists in code only behind a cloud LUNA_MODEL_URL + LUNA_API_KEY; dev-model cloud also requires LUNA_AGENT_ALLOW_CLOUD=1. Live config has none of these. Code safeguard: cross-session memory excerpts are never sent to a cloud model. Storage is local SQLite (~/Library/Application Support/ORBIT/data/luna.sqlite); cloud memory not configured.');
INSERT INTO steps VALUES(5,1,'jason',5,'Record the verdict as Luna''s verified P0-1 posture in the project record','consequential','done','','Verdict recorded in goal files/Luna-P0-1-Verification-2026-10-13.md and in MEMORY.md, on Jason''s approval given 2026-10-13 21:42 EDT.');
INSERT INTO steps VALUES(6,2,'jason',1,'Fetch PR #66 head into a fresh local clone and locate the verification call site','routine','done','','Fresh clone at PR #66 head 357f8fca (the exact head Codex verified). Defect site: luna/job_operations.py run_once, lines 36-44 — verify_local_health(job id) is wrapped in except (ValueError, OSError) only; verify_local_health persists events via SQLite (luna/result_verification.py, core.connect), so sqlite3.OperationalError escapes and aborts run_once before core.record_agent_run — exactly Codex''s FAIL.');
INSERT INTO steps VALUES(7,2,'jason',2,'Write a regression test that makes verification raise sqlite3.OperationalError and shows the worker aborting','routine','done','','Regression test added to tests/test_result_verification.py (test_worker_survives_verifier_database_error): monkeypatches verify_local_health to raise sqlite3.OperationalError(''database is locked''). Against unfixed PR #66 code it FAILS with the OperationalError propagating out of run_once — Codex''s defect reproduced locally (pytest, Python 3.12.3).');
INSERT INTO steps VALUES(8,2,'jason',3,'Broaden exception handling around the optional verifier so verification failure is recorded, never fatal','routine','done','','Fix in luna/job_operations.py: added import sqlite3 and broadened the optional-verifier guard to except (ValueError, OSError, sqlite3.Error), matching the code''s stated intent (observation is optional; the durable worker result remains available). Regression test now passes; tests/test_result_verification.py 7/7.');
INSERT INTO steps VALUES(9,2,'jason',4,'Run the full PR test suite locally and confirm green','routine','done','','Full suite run locally (the run Codex''s environment could not do): compileall OK; pytest on PR #66 head WITH fix = 509 passed / 29 failed; pristine head baseline = 508 passed / 29 failed with an IDENTICAL failure set (pre-existing environment dependency drift in unrelated model/egress tests; PR''s exact-head CI was green). Net effect of the fix: +1 passing regression test, zero regressions.');
INSERT INTO steps VALUES(10,2,'jason',5,'Push the fix commit to PR #66''s branch on GitHub','consequential','done','','Authorized by Jason: he chose ''Give Rowan GitHub access to push it'', completed GitHub OAuth + App installation scoped to Orbit-core only, and approved the write confirmation. Pushed via the official GitHub connector (push_files) to branch feature/p0-2-source-health-verification-20261013. New head 544bbf49f294d61ee4933e68a7a264246a367239, parent 357f8fca (the Codex-verified PR #66 head). Read-back verification: both files at 544bbf49 match the locally tested commit 55f1d19 byte-for-byte (job_operations.py 2645 chars; test_result_verification.py 8454 chars). PR #66 remains open and unmerged.');
INSERT INTO steps VALUES(11,3,'jason',1,'Verify the broker routes the job to an eligible free provider','routine','done','','Broker route check for needs requests=1, tokens=2000 returned groq (the only seeded provider covering both units with known quota; Gemini/Mistral unknown-quota and never routed, GitHub Models retired, Cohere eval-only).');
INSERT INTO steps VALUES(12,3,'jason',2,'Execute a live dispatch through the Groq connector and capture the response','routine','done','','Live dispatch via custom.groq connector (surrogate credential, real key swapped in at egress; helper groq_chat.py). Response from groq/openai/gpt-oss-120b: ''Luna v2 is a mission-management platform that tracks approvals and receipts, using a broker to automatically consume free AI-provider tiers while meticulously accounting for every token used.'' Usage recorded under mission 3: 1 request (usage row 3, ledger entry 3), 199 tokens (usage row 4, ledger entry 4). An earlier unattributed smoke call also succeeded (usage rows 1-2: 1 request, 168 tokens). Two earlier failed attempts (Cloudflare 1010 UA block; wrong model id gpt-oss-120b) recorded ZERO usage, proving failed calls never touch the ledger.');
INSERT INTO steps VALUES(13,3,'jason',3,'Verify the ledger and allocations reflect the spend','routine','done','','Allocations after both live calls: groq requests 998/1000 remaining, tokens 199633/200000 remaining (200000 - 168 smoke - 199 mission 3 = 199633, exact). Ledger tail shows all four entries with cost_avoided 0.0 (no invented dollar savings). Fail-closed rule verified live: ineligible needs never reach the transport (unit tests) and failed HTTP calls record nothing (observed twice).');
INSERT INTO steps VALUES(14,4,'jason',1,'Scout reads the Orbit-core README and STATE.json and answers with a cited digest','routine','done','scout digest (run 1)',replace('**Answer**  \nThe project describes itself as **“ORBIT / Luna – THRONE,”** a Luna AI that runs exclusively on a Mac M4 mini called THRONE and is served locally via a dashboard [Source 1].  \nIts `STATE.json` file records the **current published release as `pojo.2`** (with a specific main‑branch SHA) [Source 2].  \nThe two sources diverge on the status of the installed candidate: the README claims the installed Mac candidate is already **ahead of the published main** [Source 1], whereas the state file notes that the host’s live state is **“NOT_CHECKED_THIS_SESSION”** and that the installed status is only historical until it is verified [Source 2].  \n\n**Key findings**\n- **Project identity** – Described as “ORBIT / Luna — THRONE,” a local‑only dashboard on a dedicated Mac M4 mini [Source 1].\n- **Published state claim** – `STATE.json` lists `"published_release": "pojo.2"` as the current released version [Source 2].\n- **Point of disagreement** –  \n  - README: *“The installed Mac candidate is … ahead of published main.”* [Source 1]  \n  - STATE file: *`"host_live_state": "NOT_CHECKED_THIS_SESSION"`* and *“installed status is historical until verified.”* [Source 2]  \n\n**Sources**\n1. https://raw.githubusercontent.com/jmann358/Orbit-core/main/README.md  \n2. https://raw.githubusercontent.com/jmann358/Orbit-core/main/docs/orbit/STATE.json','\n',char(10)));
INSERT INTO steps VALUES(15,4,'jason',2,'Rowan verifies Scout''s digest against the two sources','routine','done','','Rowan verified every quoted claim against the live sources 2026-10-13: STATE.json contains published_release pojo.2, published_main_sha baf96abff8105b89e7b4c924ff03921f084923b5, candidate_pr pull/58, host_live_state NOT_CHECKED_THIS_SESSION, and the note ''installed status is historical until verified''; README contains ''it is ahead of published main''. Digest accurate and correctly cited. One limit: Scout could not flag that baf96ab is stale vs actual main b707f80 — unknowable from the two sources alone.');
INSERT INTO steps VALUES(16,5,'jason',1,'Run Guardian scan over Luna real state','routine','done','Guardian scan run','guardian scan filed 1 info suggestion (id 1): mission 5 itself open with 3 undone steps — expected mid-routine; no warnings or criticals');
INSERT INTO steps VALUES(17,5,'jason',2,'Run Watchman health check','routine','done','Watchman health check run','watchman report 2: overall healthy — db integrity ok, ledger reconciles, receipt coverage complete, 0 failed runs');
INSERT INTO steps VALUES(18,5,'jason',3,'Run Quartermaster resource report','routine','done','Quartermaster report run','groq 4 requests / 5,117 tokens used (2.6% of daily free), route pick groq, $0 spend; totals reconcile with ledger');
INSERT INTO steps VALUES(19,6,'jason',1,'Run Builder on a demo project in its sandbox and record the outcome','routine','done','','Builder run 1: Groq drafted the change in a disposable sandbox; project tests exit 0; 6-line diff stored on the run for review; original project verified untouched');
CREATE TABLE approvals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id    INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    owner      TEXT NOT NULL,
    decision   TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason     TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL
, category TEXT DEFAULT 'other', risk_ack INTEGER DEFAULT 0);
INSERT INTO approvals VALUES(1,5,'jason','approve','','2026-10-14T01:43:05+00:00','other',0);
INSERT INTO approvals VALUES(2,10,'jason','approve','','2026-10-14T02:05:57+00:00','other',0);
CREATE TABLE receipts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  INTEGER NOT NULL UNIQUE REFERENCES missions(id) ON DELETE CASCADE,
    owner       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
INSERT INTO receipts VALUES(1,1,'jason',replace('Mission ''P0-1 verification: installed Luna egress and memory posture'' closed: 5 done, 0 skipped.\n- step 1: Inspect the launcher (start_luna_agent.py) for model-endpoint forcing and API-key/cloud stripping [routine, done]\n- step 2: Inspect the launchd plist and service environment for endpoints, keys, and cloud flags [routine, done]\n- step 3: Inspect cloud_worker.py and core.py for outbound calls to non-local hosts [routine, done]\n- step 4: Confirm chat and memory storage is local-only (database path, no cloud memory configured) [routine, done]\n- step 5: Record the verdict as Luna''s verified P0-1 posture in the project record [consequential, done]','\n',char(10)),'{"mission": "P0-1 verification: installed Luna egress and memory posture", "owner": "jason", "outcome": "A verdict, proven from the installed source and config on THRONE, on whether Luna can silently send chat or approved memory to any cloud provider \u2014 recorded as a mission receipt.", "steps_done": 5, "steps_skipped": 0, "evidence": [{"seq": 1, "description": "Inspect the launcher (start_luna_agent.py) for model-endpoint forcing and API-key/cloud stripping", "kind": "routine", "status": "done", "evidence": "Launcher read in full (211 lines): binds 127.0.0.1:8000 only; --self-build forces LUNA_MODEL_URL=http://127.0.0.1:11434/v1 and pops LUNA_API_KEY and LUNA_AGENT_ALLOW_CLOUD from env; LUNA_CLOUD_MODE=1 makes it refuse to start; readiness reports cloud_deployed=False, remote_access=False.", "result": ""}, {"seq": 2, "description": "Inspect the launchd plist and service environment for endpoints, keys, and cloud flags", "kind": "routine", "status": "done", "evidence": "com.orbit.luna.plist read: live env contains only LUNA_DB_PATH (local sqlite), LUNA_SERVICE_MODE=1, PATH, PYTHONUNBUFFERED \u2014 no API keys, no cloud endpoints, no cloud flags.", "result": ""}, {"seq": 3, "description": "Inspect cloud_worker.py and core.py for outbound calls to non-local hosts", "kind": "routine", "status": "done", "evidence": "scripts/cloud_worker.py + luna/cloud_worker.py read and grepped: despite the name, the worker is a local SQLite job queue (cloud_jobs table) with zero network calls; handlers allowlisted (heartbeat, project_health, development_draft). Latent path: draft-PR publishing needs LUNA_GITHUB_PR_AUTO_ENABLED=1 \u2014 not set in the live env.", "result": ""}, {"seq": 4, "description": "Confirm chat and memory storage is local-only (database path, no cloud memory configured)", "kind": "routine", "status": "done", "evidence": "core.py + developer_model.py grepped and read: cloud chat exists in code only behind a cloud LUNA_MODEL_URL + LUNA_API_KEY; dev-model cloud also requires LUNA_AGENT_ALLOW_CLOUD=1. Live config has none of these. Code safeguard: cross-session memory excerpts are never sent to a cloud model. Storage is local SQLite (~/Library/Application Support/ORBIT/data/luna.sqlite); cloud memory not configured.", "result": ""}, {"seq": 5, "description": "Record the verdict as Luna''s verified P0-1 posture in the project record", "kind": "consequential", "status": "done", "evidence": "Verdict recorded in goal files/Luna-P0-1-Verification-2026-10-13.md and in MEMORY.md, on Jason''s approval given 2026-10-13 21:42 EDT.", "result": ""}]}','2026-10-14T01:43:05+00:00');
INSERT INTO receipts VALUES(2,2,'jason',replace('Mission ''Fix PR #66''s SQLite defect (hurdle 1: unreliable verification)'' closed: 5 done, 0 skipped.\n- step 1: Fetch PR #66 head into a fresh local clone and locate the verification call site [routine, done]\n- step 2: Write a regression test that makes verification raise sqlite3.OperationalError and shows the worker aborting [routine, done]\n- step 3: Broaden exception handling around the optional verifier so verification failure is recorded, never fatal [routine, done]\n- step 4: Run the full PR test suite locally and confirm green [routine, done]\n- step 5: Push the fix commit to PR #66''s branch on GitHub [consequential, done]','\n',char(10)),'{"mission": "Fix PR #66''s SQLite defect (hurdle 1: unreliable verification)", "owner": "jason", "outcome": "PR #66''s optional verifier can no longer abort the worker: a database error during verification leaves the completed job result intact, proven by a new regression test and the PR suite passing locally.", "steps_done": 5, "steps_skipped": 0, "evidence": [{"seq": 1, "description": "Fetch PR #66 head into a fresh local clone and locate the verification call site", "kind": "routine", "status": "done", "evidence": "Fresh clone at PR #66 head 357f8fca (the exact head Codex verified). Defect site: luna/job_operations.py run_once, lines 36-44 \u2014 verify_local_health(job id) is wrapped in except (ValueError, OSError) only; verify_local_health persists events via SQLite (luna/result_verification.py, core.connect), so sqlite3.OperationalError escapes and aborts run_once before core.record_agent_run \u2014 exactly Codex''s FAIL.", "result": ""}, {"seq": 2, "description": "Write a regression test that makes verification raise sqlite3.OperationalError and shows the worker aborting", "kind": "routine", "status": "done", "evidence": "Regression test added to tests/test_result_verification.py (test_worker_survives_verifier_database_error): monkeypatches verify_local_health to raise sqlite3.OperationalError(''database is locked''). Against unfixed PR #66 code it FAILS with the OperationalError propagating out of run_once \u2014 Codex''s defect reproduced locally (pytest, Python 3.12.3).", "result": ""}, {"seq": 3, "description": "Broaden exception handling around the optional verifier so verification failure is recorded, never fatal", "kind": "routine", "status": "done", "evidence": "Fix in luna/job_operations.py: added import sqlite3 and broadened the optional-verifier guard to except (ValueError, OSError, sqlite3.Error), matching the code''s stated intent (observation is optional; the durable worker result remains available). Regression test now passes; tests/test_result_verification.py 7/7.", "result": ""}, {"seq": 4, "description": "Run the full PR test suite locally and confirm green", "kind": "routine", "status": "done", "evidence": "Full suite run locally (the run Codex''s environment could not do): compileall OK; pytest on PR #66 head WITH fix = 509 passed / 29 failed; pristine head baseline = 508 passed / 29 failed with an IDENTICAL failure set (pre-existing environment dependency drift in unrelated model/egress tests; PR''s exact-head CI was green). Net effect of the fix: +1 passing regression test, zero regressions.", "result": ""}, {"seq": 5, "description": "Push the fix commit to PR #66''s branch on GitHub", "kind": "consequential", "status": "done", "evidence": "Authorized by Jason: he chose ''Give Rowan GitHub access to push it'', completed GitHub OAuth + App installation scoped to Orbit-core only, and approved the write confirmation. Pushed via the official GitHub connector (push_files) to branch feature/p0-2-source-health-verification-20261013. New head 544bbf49f294d61ee4933e68a7a264246a367239, parent 357f8fca (the Codex-verified PR #66 head). Read-back verification: both files at 544bbf49 match the locally tested commit 55f1d19 byte-for-byte (job_operations.py 2645 chars; test_result_verification.py 8454 chars). PR #66 remains open and unmerged.", "result": ""}]}','2026-10-14T02:05:58+00:00');
INSERT INTO receipts VALUES(3,3,'jason',replace('Mission ''First live provider dispatch through the broker (P1-CREDIT proof)'' closed: 3 done, 0 skipped.\n- step 1: Verify the broker routes the job to an eligible free provider [routine, done]\n- step 2: Execute a live dispatch through the Groq connector and capture the response [routine, done]\n- step 3: Verify the ledger and allocations reflect the spend [routine, done]','\n',char(10)),'{"mission": "First live provider dispatch through the broker (P1-CREDIT proof)", "owner": "jason", "outcome": "Luna v2 routes a real prompt to a free provider, returns the answer, and accounts every token in the resource ledger - /bin/bash spent.", "steps_done": 3, "steps_skipped": 0, "evidence": [{"seq": 1, "description": "Verify the broker routes the job to an eligible free provider", "kind": "routine", "status": "done", "evidence": "Broker route check for needs requests=1, tokens=2000 returned groq (the only seeded provider covering both units with known quota; Gemini/Mistral unknown-quota and never routed, GitHub Models retired, Cohere eval-only).", "result": ""}, {"seq": 2, "description": "Execute a live dispatch through the Groq connector and capture the response", "kind": "routine", "status": "done", "evidence": "Live dispatch via custom.groq connector (surrogate credential, real key swapped in at egress; helper groq_chat.py). Response from groq/openai/gpt-oss-120b: ''Luna v2 is a mission-management platform that tracks approvals and receipts, using a broker to automatically consume free AI-provider tiers while meticulously accounting for every token used.'' Usage recorded under mission 3: 1 request (usage row 3, ledger entry 3), 199 tokens (usage row 4, ledger entry 4). An earlier unattributed smoke call also succeeded (usage rows 1-2: 1 request, 168 tokens). Two earlier failed attempts (Cloudflare 1010 UA block; wrong model id gpt-oss-120b) recorded ZERO usage, proving failed calls never touch the ledger.", "result": ""}, {"seq": 3, "description": "Verify the ledger and allocations reflect the spend", "kind": "routine", "status": "done", "evidence": "Allocations after both live calls: groq requests 998/1000 remaining, tokens 199633/200000 remaining (200000 - 168 smoke - 199 mission 3 = 199633, exact). Ledger tail shows all four entries with cost_avoided 0.0 (no invented dollar savings). Fail-closed rule verified live: ineligible needs never reach the transport (unit tests) and failed HTTP calls record nothing (observed twice).", "result": ""}]}','2026-10-14T02:21:43+00:00');
INSERT INTO receipts VALUES(4,4,'jason',replace('Mission ''Scout''s first job — what Orbit-core says it is, and where its own records disagree'' closed: 2 done, 0 skipped.\n- step 1: Scout reads the Orbit-core README and STATE.json and answers with a cited digest [routine, done]\n- step 2: Rowan verifies Scout''s digest against the two sources [routine, done]','\n',char(10)),'{"mission": "Scout''s first job \u2014 what Orbit-core says it is, and where its own records disagree", "owner": "jason", "outcome": "A source-cited digest from Luna''s Research Scout, verified by Rowan against the sources, closed with a receipt", "steps_done": 2, "steps_skipped": 0, "evidence": [{"seq": 1, "description": "Scout reads the Orbit-core README and STATE.json and answers with a cited digest", "kind": "routine", "status": "done", "evidence": "**Answer**  \nThe project describes itself as **\u201cORBIT\u202f/\u202fLuna \u2013 THRONE,\u201d** a Luna AI that runs exclusively on a Mac\u202fM4 mini called THRONE and is served locally via a dashboard\u202f[Source\u202f1].  \nIts\u202f`STATE.json` file records the **current published release as\u202f`pojo.2`** (with a specific main\u2011branch SHA)\u202f[Source\u202f2].  \nThe two sources diverge on the status of the installed candidate: the README claims the installed Mac candidate is already **ahead of the published main**\u202f[Source\u202f1], whereas the state file notes that the host\u2019s live state is **\u201cNOT_CHECKED_THIS_SESSION\u201d** and that the installed status is only historical until it is verified\u202f[Source\u202f2].  \n\n**Key findings**\n- **Project identity** \u2013 Described as \u201cORBIT\u202f/\u202fLuna \u2014 THRONE,\u201d a local\u2011only dashboard on a dedicated Mac\u202fM4 mini\u202f[Source\u202f1].\n- **Published state claim** \u2013 `STATE.json` lists `\"published_release\": \"pojo.2\"` as the current released version\u202f[Source\u202f2].\n- **Point of disagreement** \u2013  \n  - README: *\u201cThe installed Mac candidate is \u2026 ahead of published main.\u201d*\u202f[Source\u202f1]  \n  - STATE file: *`\"host_live_state\": \"NOT_CHECKED_THIS_SESSION\"`* and *\u201cinstalled status is historical until verified.\u201d*\u202f[Source\u202f2]  \n\n**Sources**\n1. https://raw.githubusercontent.com/jmann358/Orbit-core/main/README.md  \n2. https://raw.githubusercontent.com/jmann358/Orbit-core/main/docs/orbit/STATE.json", "result": "scout digest (run 1)"}, {"seq": 2, "description": "Rowan verifies Scout''s digest against the two sources", "kind": "routine", "status": "done", "evidence": "Rowan verified every quoted claim against the live sources 2026-10-13: STATE.json contains published_release pojo.2, published_main_sha baf96abff8105b89e7b4c924ff03921f084923b5, candidate_pr pull/58, host_live_state NOT_CHECKED_THIS_SESSION, and the note ''installed status is historical until verified''; README contains ''it is ahead of published main''. Digest accurate and correctly cited. One limit: Scout could not flag that baf96ab is stale vs actual main b707f80 \u2014 unknowable from the two sources alone.", "result": ""}]}','2026-10-14T02:37:18+00:00');
INSERT INTO receipts VALUES(5,5,'jason',replace('Mission ''Daily team health routine'' closed: 3 done, 0 skipped.\n- step 1: Run Guardian scan over Luna real state [routine, done]\n- step 2: Run Watchman health check [routine, done]\n- step 3: Run Quartermaster resource report [routine, done]','\n',char(10)),'{"mission": "Daily team health routine", "owner": "jason", "outcome": "Scheduled run of routine ''daily-team-health'' (daily); created by scheduler tick at 2026-10-14T03:11:39+00:00.", "steps_done": 3, "steps_skipped": 0, "evidence": [{"seq": 1, "description": "Run Guardian scan over Luna real state", "kind": "routine", "status": "done", "evidence": "guardian scan filed 1 info suggestion (id 1): mission 5 itself open with 3 undone steps \u2014 expected mid-routine; no warnings or criticals", "result": "Guardian scan run"}, {"seq": 2, "description": "Run Watchman health check", "kind": "routine", "status": "done", "evidence": "watchman report 2: overall healthy \u2014 db integrity ok, ledger reconciles, receipt coverage complete, 0 failed runs", "result": "Watchman health check run"}, {"seq": 3, "description": "Run Quartermaster resource report", "kind": "routine", "status": "done", "evidence": "groq 4 requests / 5,117 tokens used (2.6% of daily free), route pick groq, $0 spend; totals reconcile with ledger", "result": "Quartermaster report run"}]}','2026-10-14T03:11:51+00:00');
INSERT INTO receipts VALUES(6,6,'jason',replace('Mission ''Builder''s first live draft'' closed: 1 done, 0 skipped.\n- step 1: Run Builder on a demo project in its sandbox and record the outcome [routine, done]','\n',char(10)),'{"mission": "Builder''s first live draft", "owner": "jason", "outcome": "", "steps_done": 1, "steps_skipped": 0, "evidence": [{"seq": 1, "description": "Run Builder on a demo project in its sandbox and record the outcome", "kind": "routine", "status": "done", "evidence": "Builder run 1: Groq drafted the change in a disposable sandbox; project tests exit 0; 6-line diff stored on the run for review; original project verified untouched", "result": ""}]}','2026-10-14T03:25:32+00:00');
CREATE TABLE value_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    owner       TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('money', 'hours')),
    amount      REAL NOT NULL,
    baseline_note TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE broker_providers (
    provider           TEXT NOT NULL,
    owner              TEXT NOT NULL,
    unit               TEXT NOT NULL,
    allowance          REAL,          -- NULL = unknown (never routed on)
    period             TEXT NOT NULL CHECK (period IN ('daily', 'monthly')),
    reset_note         TEXT NOT NULL DEFAULT '',
    hard_stop          INTEGER NOT NULL DEFAULT 1,
    api                INTEGER NOT NULL DEFAULT 1,
    status             TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'retired', 'evaluation_only')),
    production_allowed INTEGER NOT NULL DEFAULT 1,
    source_url         TEXT NOT NULL DEFAULT '',
    notes              TEXT NOT NULL DEFAULT '',
    updated_at         TEXT NOT NULL, model TEXT DEFAULT NULL,
    PRIMARY KEY (provider, unit, owner)
);
INSERT INTO broker_providers VALUES('groq','jason','tokens',200000.0,'daily','daily reset; 8,000 tokens/min minute cap also applies (not tracked)',1,1,'active',1,'https://console.groq.com/docs/rate-limits','gpt-oss-120b: 1,000 req/day, 30 req/min, 200,000 tokens/day, 8,000 tokens/min','2026-10-14T02:20:55+00:00','openai/gpt-oss-120b');
INSERT INTO broker_providers VALUES('groq','jason','requests',1000.0,'daily','daily reset; 30 req/min minute cap also applies (not tracked)',1,1,'active',1,'https://console.groq.com/docs/rate-limits','gpt-oss-120b figures; model-dependent','2026-10-14T02:20:55+00:00','openai/gpt-oss-120b');
INSERT INTO broker_providers VALUES('gemini','jason','tokens',NULL,'daily','daily, resets at midnight Pacific (tracked as UTC day)',1,1,'active',1,'https://ai.google.dev/gemini-api/docs/pricing','free input/output tokens for eligible models incl. Gemini 3.1 Flash-Lite; exact quota unknown, varies by model/project','2026-10-14T02:20:55+00:00',NULL);
INSERT INTO broker_providers VALUES('openrouter','jason','requests',50.0,'daily','daily reset at 00:00 UTC; 20 req/min cap also applies (not tracked)',1,1,'active',1,'https://openrouter.ai/docs/api_reference/limits','models designated :free only; paid fallbacks excluded','2026-10-14T02:20:55+00:00',NULL);
INSERT INTO broker_providers VALUES('cloudflare','jason','neurons',10000.0,'daily','daily reset at 00:00 UTC',1,1,'active',1,'https://developers.cloudflare.com/workers-ai/platform/pricing/','10,000 neurons/day across eligible models on Workers Free','2026-10-14T02:20:55+00:00',NULL);
INSERT INTO broker_providers VALUES('mistral','jason','tokens',NULL,'monthly','monthly usage allowance; per-second/minute limits also apply',1,1,'active',1,'https://docs.mistral.ai/admin/billing-usage/usage-limits','free API mode; exact token allowance unknown, org/model-specific','2026-10-14T02:20:55+00:00',NULL);
INSERT INTO broker_providers VALUES('huggingface','jason','credits',0.100000000000000005,'monthly','monthly renewal; subject to change',1,1,'active',1,'https://huggingface.co/docs/inference-providers/pricing','$0.10 inference credits/month; hard stop if no credits purchased','2026-10-14T02:20:55+00:00',NULL);
INSERT INTO broker_providers VALUES('cohere','jason','calls',1000.0,'monthly','monthly quota; trial-key expiration unknown',1,1,'evaluation_only',0,'https://docs.cohere.com/v2/docs/rate-limits','trial key is evaluation/testing only, NOT production use — never routed','2026-10-14T02:20:55+00:00',NULL);
INSERT INTO broker_providers VALUES('github_models','jason','tokens',NULL,'daily','permanently retired',0,0,'retired',0,'https://github.blog/changelog/2026-07-30-github-models-is-now-retired/','NO free API offer; service fully retired 2026-07-30 — never routed','2026-10-14T02:20:55+00:00',NULL);
CREATE TABLE broker_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    provider   TEXT NOT NULL,
    unit       TEXT NOT NULL,
    amount     REAL NOT NULL,
    used_at    TEXT NOT NULL,
    mission_id INTEGER REFERENCES missions(id) ON DELETE SET NULL,
    note       TEXT NOT NULL DEFAULT ''
);
INSERT INTO broker_usage VALUES(1,'jason','groq','requests',1.0,'2026-10-14T02:21:09+00:00',NULL,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(2,'jason','groq','tokens',168.0,'2026-10-14T02:21:09+00:00',NULL,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(3,'jason','groq','requests',1.0,'2026-10-14T02:21:34+00:00',3,'mission 3: first live dispatch proof');
INSERT INTO broker_usage VALUES(4,'jason','groq','tokens',199.0,'2026-10-14T02:21:34+00:00',3,'mission 3: first live dispatch proof');
INSERT INTO broker_usage VALUES(5,'jason','groq','requests',1.0,'2026-10-14T02:37:00+00:00',4,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(6,'jason','groq','tokens',4636.0,'2026-10-14T02:37:00+00:00',4,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(7,'jason','groq','requests',1.0,'2026-10-14T03:11:29+00:00',NULL,'armorer probe: tool health check');
INSERT INTO broker_usage VALUES(8,'jason','groq','tokens',114.0,'2026-10-14T03:11:29+00:00',NULL,'armorer probe: tool health check');
INSERT INTO broker_usage VALUES(9,'jason','groq','requests',1.0,'2026-10-14T03:25:02+00:00',NULL,'designer proposal ''Deep Space Draft''');
INSERT INTO broker_usage VALUES(10,'jason','groq','tokens',1022.0,'2026-10-14T03:25:03+00:00',NULL,'designer proposal ''Deep Space Draft''');
INSERT INTO broker_usage VALUES(11,'jason','groq','requests',1.0,'2026-10-14T03:25:24+00:00',6,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(12,'jason','groq','tokens',318.0,'2026-10-14T03:25:24+00:00',6,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(13,'jason','groq','requests',1.0,'2026-10-14T06:16:29+00:00',NULL,'live dispatch: groq/openai/gpt-oss-120b');
INSERT INTO broker_usage VALUES(14,'jason','groq','tokens',765.0,'2026-10-14T06:16:29+00:00',NULL,'live dispatch: groq/openai/gpt-oss-120b');
CREATE TABLE broker_ledger (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner              TEXT NOT NULL,
    provider           TEXT NOT NULL,
    unit               TEXT NOT NULL,
    amount             REAL NOT NULL,
    allocation_used_pct REAL NOT NULL DEFAULT 0,
    cost_avoided       REAL NOT NULL DEFAULT 0,
    note               TEXT NOT NULL DEFAULT '',
    mission_id         INTEGER REFERENCES missions(id) ON DELETE SET NULL,
    created_at         TEXT NOT NULL
);
INSERT INTO broker_ledger VALUES(1,'jason','groq','requests',1.0,0.100000000000000005,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T02:21:09+00:00');
INSERT INTO broker_ledger VALUES(2,'jason','groq','tokens',168.0,0.0840000000000000052,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T02:21:09+00:00');
INSERT INTO broker_ledger VALUES(3,'jason','groq','requests',1.0,0.100000000000000005,0.0,'mission 3: first live dispatch proof free allocation used; $0 spend baseline — no dollar savings claimed',3,'2026-10-14T02:21:34+00:00');
INSERT INTO broker_ledger VALUES(4,'jason','groq','tokens',199.0,0.099500000000000005,0.0,'mission 3: first live dispatch proof free allocation used; $0 spend baseline — no dollar savings claimed',3,'2026-10-14T02:21:34+00:00');
INSERT INTO broker_ledger VALUES(5,'jason','groq','requests',1.0,0.100000000000000005,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',4,'2026-10-14T02:37:00+00:00');
INSERT INTO broker_ledger VALUES(6,'jason','groq','tokens',4636.0,2.31800000000000006,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',4,'2026-10-14T02:37:00+00:00');
INSERT INTO broker_ledger VALUES(7,'jason','groq','requests',1.0,0.100000000000000005,0.0,'armorer probe: tool health check free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T03:11:29+00:00');
INSERT INTO broker_ledger VALUES(8,'jason','groq','tokens',114.0,0.0569999999999999951,0.0,'armorer probe: tool health check free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T03:11:29+00:00');
INSERT INTO broker_ledger VALUES(9,'jason','groq','requests',1.0,0.100000000000000005,0.0,'designer proposal ''Deep Space Draft'' free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T03:25:02+00:00');
INSERT INTO broker_ledger VALUES(10,'jason','groq','tokens',1022.0,0.511000000000000009,0.0,'designer proposal ''Deep Space Draft'' free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T03:25:03+00:00');
INSERT INTO broker_ledger VALUES(11,'jason','groq','requests',1.0,0.100000000000000005,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',6,'2026-10-14T03:25:24+00:00');
INSERT INTO broker_ledger VALUES(12,'jason','groq','tokens',318.0,0.159000000000000002,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',6,'2026-10-14T03:25:24+00:00');
INSERT INTO broker_ledger VALUES(13,'jason','groq','requests',1.0,0.100000000000000005,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T06:16:29+00:00');
INSERT INTO broker_ledger VALUES(14,'jason','groq','tokens',765.0,0.382500000000000006,0.0,'live dispatch: groq/openai/gpt-oss-120b free allocation used; $0 spend baseline — no dollar savings claimed',NULL,'2026-10-14T06:16:29+00:00');
CREATE TABLE specialist_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    specialist  TEXT NOT NULL,
    owner       TEXT NOT NULL,
    mission_id  INTEGER,
    step_id     INTEGER,
    question    TEXT NOT NULL DEFAULT '',
    sources_json TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'started'
                CHECK (status IN ('started', 'done', 'failed')),
    result      TEXT NOT NULL DEFAULT '',
    error       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
INSERT INTO specialist_runs VALUES(1,'scout','jason',4,14,'What does this project say it is, what does its state file claim its current published state is, and where exactly do the two sources disagree? Cite the source for each claim.','[{"url": "https://raw.githubusercontent.com/jmann358/Orbit-core/main/README.md", "ok": true, "chars": 2612}, {"url": "https://raw.githubusercontent.com/jmann358/Orbit-core/main/docs/orbit/STATE.json", "ok": true, "chars": 9123}]','done',replace('**Answer**  \nThe project describes itself as **“ORBIT / Luna – THRONE,”** a Luna AI that runs exclusively on a Mac M4 mini called THRONE and is served locally via a dashboard [Source 1].  \nIts `STATE.json` file records the **current published release as `pojo.2`** (with a specific main‑branch SHA) [Source 2].  \nThe two sources diverge on the status of the installed candidate: the README claims the installed Mac candidate is already **ahead of the published main** [Source 1], whereas the state file notes that the host’s live state is **“NOT_CHECKED_THIS_SESSION”** and that the installed status is only historical until it is verified [Source 2].  \n\n**Key findings**\n- **Project identity** – Described as “ORBIT / Luna — THRONE,” a local‑only dashboard on a dedicated Mac M4 mini [Source 1].\n- **Published state claim** – `STATE.json` lists `"published_release": "pojo.2"` as the current released version [Source 2].\n- **Point of disagreement** –  \n  - README: *“The installed Mac candidate is … ahead of published main.”* [Source 1]  \n  - STATE file: *`"host_live_state": "NOT_CHECKED_THIS_SESSION"`* and *“installed status is historical until verified.”* [Source 2]  \n\n**Sources**\n1. https://raw.githubusercontent.com/jmann358/Orbit-core/main/README.md  \n2. https://raw.githubusercontent.com/jmann358/Orbit-core/main/docs/orbit/STATE.json','\n',char(10)),'','2026-10-14T02:36:56+00:00');
CREATE TABLE guardian_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    check_name      TEXT NOT NULL,
    subject         TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    observation     TEXT NOT NULL DEFAULT '',
    evidence        TEXT NOT NULL DEFAULT '',
    proposed_action TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','acknowledged','done','declined')),
    resolution_note TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    resolved_at     TEXT,
    dedupe_key      TEXT NOT NULL
);
INSERT INTO guardian_suggestions VALUES(1,'jason','stuck_mission','mission 5','info','mission 5 ''Daily team health routine'' is open with 3 of 3 steps not done/skipped','open steps: 16 (Run Guardian scan over Luna real state), 17 (Run Watchman health check), 18 (Run Quartermaster resource report)','Rowan: investigate — if the mission is abandoned, close it (skip the dead steps); if it is real work, drive it to a receipt or hand it to a specialist.','done','Mission 5 completed and closed with receipt; the open mission Guardian flagged was the routine itself, mid-run','2026-10-14T03:11:45+00:00','2026-10-14T03:11:52+00:00','stuck_mission:mission 5');
CREATE TABLE verification_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    mission_id  INTEGER NOT NULL,
    verdict     TEXT NOT NULL CHECK (verdict IN ('pass', 'fail')),
    checks_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
INSERT INTO verification_runs VALUES(1,'jason',4,'pass','[{"check": "evidence_present", "status": "pass", "detail": "all 2 done step(s) carry evidence"}, {"check": "receipt_consistency", "status": "pass", "detail": "receipt captures the evidence of all 2 step(s) exactly"}, {"check": "usage_reconciliation", "status": "pass", "detail": "usage and ledger reconcile across 2 provider/unit pair(s) for this mission"}, {"check": "citation_reachability", "status": "info", "detail": "2 citation(s) present; not fetched (no fetcher supplied)"}]','2026-10-14T03:07:19+00:00');
INSERT INTO verification_runs VALUES(2,'jason',1,'pass','[{"check": "evidence_present", "status": "pass", "detail": "all 5 done step(s) carry evidence"}, {"check": "receipt_consistency", "status": "pass", "detail": "receipt captures the evidence of all 5 step(s) exactly"}, {"check": "usage_reconciliation", "status": "pass", "detail": "usage and ledger reconcile across 0 provider/unit pair(s) for this mission"}, {"check": "citation_reachability", "status": "info", "detail": "1 citation(s) present; not fetched (no fetcher supplied)"}]','2026-10-14T03:07:20+00:00');
INSERT INTO verification_runs VALUES(3,'jason',5,'pass','[{"check": "evidence_present", "status": "pass", "detail": "all 3 done step(s) carry evidence"}, {"check": "receipt_consistency", "status": "pass", "detail": "receipt captures the evidence of all 3 step(s) exactly"}, {"check": "usage_reconciliation", "status": "pass", "detail": "usage and ledger reconcile across 0 provider/unit pair(s) for this mission"}, {"check": "citation_reachability", "status": "info", "detail": "no citations found in step evidence"}]','2026-10-14T03:11:52+00:00');
INSERT INTO verification_runs VALUES(4,'jason',6,'pass','[{"check": "evidence_present", "status": "pass", "detail": "all 1 done step(s) carry evidence"}, {"check": "receipt_consistency", "status": "pass", "detail": "receipt captures the evidence of all 1 step(s) exactly"}, {"check": "usage_reconciliation", "status": "pass", "detail": "usage and ledger reconcile across 2 provider/unit pair(s) for this mission"}, {"check": "citation_reachability", "status": "info", "detail": "no citations found in step evidence"}]','2026-10-14T03:25:33+00:00');
CREATE TABLE qm_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_json TEXT NOT NULL DEFAULT '{}'
);
INSERT INTO qm_reports VALUES(1,'jason','2026-10-14T03:07:22+00:00','{"owner": "jason", "created_at": "2026-10-14T03:07:22+00:00", "allocations": [{"provider": "cloudflare", "unit": "neurons", "used": 0, "total": 10000.0, "remaining": 10000.0, "pct_used": 0.0, "period": "daily", "resets_in_seconds": 75157.479042, "resets_in": "20h 52m", "flags": ["USE_OR_LOSE"]}, {"provider": "groq", "unit": "requests", "used": 3.0, "total": 1000.0, "remaining": 997.0, "pct_used": 0.3, "period": "daily", "resets_in_seconds": 75157.479042, "resets_in": "20h 52m", "flags": ["USE_OR_LOSE"]}, {"provider": "groq", "unit": "tokens", "used": 5003.0, "total": 200000.0, "remaining": 194997.0, "pct_used": 2.5015, "period": "daily", "resets_in_seconds": 75157.479042, "resets_in": "20h 52m", "flags": ["USE_OR_LOSE"]}, {"provider": "huggingface", "unit": "credits", "used": 0, "total": 0.1, "remaining": 0.1, "pct_used": 0.0, "period": "monthly", "resets_in_seconds": 1543957.479042, "resets_in": "17d 20h", "flags": []}, {"provider": "openrouter", "unit": "requests", "used": 0, "total": 50.0, "remaining": 50.0, "pct_used": 0.0, "period": "daily", "resets_in_seconds": 75157.479042, "resets_in": "20h 52m", "flags": ["USE_OR_LOSE"]}], "totals": {"neurons": {"used": 0.0, "total": 10000.0, "remaining": 10000.0}, "requests": {"used": 3.0, "total": 1050.0, "remaining": 1047.0}, "tokens": {"used": 5003.0, "total": 200000.0, "remaining": 194997.0}, "credits": {"used": 0.0, "total": 0.1, "remaining": 0.1}}, "route_pick": {"eligible": true, "provider": "groq", "needs": {"requests": 1.0, "tokens": 500.0}, "remaining_after": {"requests": 996.0, "tokens": 194497.0}, "resets_in": "20h 52m", "note": "routed to groq: soonest-expiring eligible allocation; free tier, $0 spend"}}');
INSERT INTO qm_reports VALUES(2,'jason','2026-10-14T03:11:45+00:00','{"owner": "jason", "created_at": "2026-10-14T03:11:45+00:00", "allocations": [{"provider": "cloudflare", "unit": "neurons", "used": 0, "total": 10000.0, "remaining": 10000.0, "pct_used": 0.0, "period": "daily", "resets_in_seconds": 74894.10848, "resets_in": "20h 48m", "flags": ["USE_OR_LOSE"]}, {"provider": "groq", "unit": "requests", "used": 4.0, "total": 1000.0, "remaining": 996.0, "pct_used": 0.4, "period": "daily", "resets_in_seconds": 74894.10848, "resets_in": "20h 48m", "flags": ["USE_OR_LOSE"]}, {"provider": "groq", "unit": "tokens", "used": 5117.0, "total": 200000.0, "remaining": 194883.0, "pct_used": 2.5585, "period": "daily", "resets_in_seconds": 74894.10848, "resets_in": "20h 48m", "flags": ["USE_OR_LOSE"]}, {"provider": "huggingface", "unit": "credits", "used": 0, "total": 0.1, "remaining": 0.1, "pct_used": 0.0, "period": "monthly", "resets_in_seconds": 1543694.10848, "resets_in": "17d 20h", "flags": []}, {"provider": "openrouter", "unit": "requests", "used": 0, "total": 50.0, "remaining": 50.0, "pct_used": 0.0, "period": "daily", "resets_in_seconds": 74894.10848, "resets_in": "20h 48m", "flags": ["USE_OR_LOSE"]}], "totals": {"neurons": {"used": 0.0, "total": 10000.0, "remaining": 10000.0}, "requests": {"used": 4.0, "total": 1050.0, "remaining": 1046.0}, "tokens": {"used": 5117.0, "total": 200000.0, "remaining": 194883.0}, "credits": {"used": 0.0, "total": 0.1, "remaining": 0.1}}, "route_pick": {"eligible": true, "provider": "groq", "needs": {"requests": 1.0, "tokens": 500.0}, "remaining_after": {"requests": 995.0, "tokens": 194383.0}, "resets_in": "20h 48m", "note": "routed to groq: soonest-expiring eligible allocation; free tier, $0 spend"}}');
INSERT INTO qm_reports VALUES(3,'jason','2026-10-14T03:25:44+00:00','{"owner": "jason", "created_at": "2026-10-14T03:25:44+00:00", "allocations": [{"provider": "cloudflare", "unit": "neurons", "used": 0, "total": 10000.0, "remaining": 10000.0, "pct_used": 0.0, "period": "daily", "resets_in_seconds": 74055.353511, "resets_in": "20h 34m", "flags": ["USE_OR_LOSE"]}, {"provider": "groq", "unit": "requests", "used": 6.0, "total": 1000.0, "remaining": 994.0, "pct_used": 0.6, "period": "daily", "resets_in_seconds": 74055.353511, "resets_in": "20h 34m", "flags": ["USE_OR_LOSE"]}, {"provider": "groq", "unit": "tokens", "used": 6457.0, "total": 200000.0, "remaining": 193543.0, "pct_used": 3.2285, "period": "daily", "resets_in_seconds": 74055.353511, "resets_in": "20h 34m", "flags": ["USE_OR_LOSE"]}, {"provider": "huggingface", "unit": "credits", "used": 0, "total": 0.1, "remaining": 0.1, "pct_used": 0.0, "period": "monthly", "resets_in_seconds": 1542855.353511, "resets_in": "17d 20h", "flags": []}, {"provider": "openrouter", "unit": "requests", "used": 0, "total": 50.0, "remaining": 50.0, "pct_used": 0.0, "period": "daily", "resets_in_seconds": 74055.353511, "resets_in": "20h 34m", "flags": ["USE_OR_LOSE"]}], "totals": {"neurons": {"used": 0.0, "total": 10000.0, "remaining": 10000.0}, "requests": {"used": 6.0, "total": 1050.0, "remaining": 1044.0}, "tokens": {"used": 6457.0, "total": 200000.0, "remaining": 193543.0}, "credits": {"used": 0.0, "total": 0.1, "remaining": 0.1}}, "route_pick": {"eligible": true, "provider": "groq", "needs": {"requests": 1.0, "tokens": 500.0}, "remaining_after": {"requests": 993.0, "tokens": 193043.0}, "resets_in": "20h 34m", "note": "routed to groq: soonest-expiring eligible allocation; free tier, $0 spend"}}');
CREATE TABLE watchman_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('healthy','degraded','critical')),
    checks_json TEXT NOT NULL DEFAULT '[]'
);
INSERT INTO watchman_reports VALUES(1,'jason','2026-10-14T03:07:22+00:00','healthy','[{"check": "db_integrity", "status": "pass", "detail": "PRAGMA integrity_check ok"}, {"check": "ledger_reconciliation", "status": "pass", "detail": "2 provider/unit pair(s) reconcile (usage totals match ledger totals)"}, {"check": "receipt_coverage", "status": "pass", "detail": "all 4 closed mission(s) have exactly one receipt"}, {"check": "specialist_failure_share", "status": "pass", "detail": "0 failed of 1 recent runs (0%)"}, {"check": "guardian_inbox", "status": "info", "detail": "no open suggestions"}]');
INSERT INTO watchman_reports VALUES(2,'jason','2026-10-14T03:11:45+00:00','healthy','[{"check": "db_integrity", "status": "pass", "detail": "PRAGMA integrity_check ok"}, {"check": "ledger_reconciliation", "status": "pass", "detail": "2 provider/unit pair(s) reconcile (usage totals match ledger totals)"}, {"check": "receipt_coverage", "status": "pass", "detail": "all 4 closed mission(s) have exactly one receipt"}, {"check": "specialist_failure_share", "status": "pass", "detail": "0 failed of 1 recent runs (0%)"}, {"check": "guardian_inbox", "status": "info", "detail": "open suggestions: 0 critical, 0 warning, 1 info"}]');
CREATE TABLE sentinel_audits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    findings_json TEXT NOT NULL DEFAULT '[]',
    finding_count INTEGER NOT NULL DEFAULT 0
);
INSERT INTO sentinel_audits VALUES(1,'jason','2026-10-14T03:07:23+00:00','[]',0);
CREATE TABLE armorer_tools (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT '',
    location   TEXT NOT NULL DEFAULT '',
    doc_path   TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'unknown'
               CHECK (status IN ('unknown', 'ok', 'broken')),
    detail     TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT,
    UNIQUE (owner, name)
);
INSERT INTO armorer_tools VALUES(1,'jason','groq-connector-helper','helper','~/workspace/custom-connectors/custom.groq/bin/groq_chat.py','~/workspace/custom-connectors/custom.groq/CONNECTOR.md','ok','location present: ~/workspace/custom-connectors/custom.groq/bin/groq_chat.py; doc present: ~/workspace/custom-connectors/custom.groq/CONNECTOR.md; route check: groq routable for reference job (1 request, 500 tokens); probe ok: live ping via groq/openai/gpt-oss-120b','2026-10-14T03:11:27+00:00');
INSERT INTO armorer_tools VALUES(2,'jason','github-connector-cli','cli','/opt/hatch/bin/github','/opt/hatch/connectors/github/CONNECTOR.md','ok','location present: /opt/hatch/bin/github; doc present: /opt/hatch/connectors/github/CONNECTOR.md','2026-10-14T03:11:27+00:00');
INSERT INTO armorer_tools VALUES(3,'jason','luna-v2-cli','cli','~/workspace/luna-v2/luna_v2/cli.py','~/workspace/luna-v2/README.md','ok','location present: ~/workspace/luna-v2/luna_v2/cli.py; doc present: ~/workspace/luna-v2/README.md','2026-10-14T03:11:27+00:00');
CREATE TABLE memory_entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    text          TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT '',
    approved_by   TEXT NOT NULL,
    approval_note TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    retired_at    TEXT,
    retire_reason TEXT NOT NULL DEFAULT ''
);
INSERT INTO memory_entries VALUES(1,'jason','Jason''s rule: Luna remembers only approved context. Nothing is filed as memory without a recorded approver.','Jason''s Luna v2 design direction, 2026-10-13','jason','First Archivist filing on the real database; proves the gate live','2026-10-14T03:11:34+00:00',NULL,'');
CREATE TABLE schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner          TEXT NOT NULL,
    name           TEXT NOT NULL,
    mission_title  TEXT NOT NULL,
    steps_json     TEXT NOT NULL,
    cadence        TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly')),
    next_run_at    TEXT NOT NULL,
    last_run_at    TEXT NOT NULL DEFAULT '',
    last_mission_id INTEGER,
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at     TEXT NOT NULL
);
INSERT INTO schedules VALUES(1,'jason','daily-team-health','Daily team health routine','[{"description": "Run Guardian scan over Luna real state", "kind": "routine"}, {"description": "Run Watchman health check", "kind": "routine"}, {"description": "Run Quartermaster resource report", "kind": "routine"}]','daily','2026-10-15T03:11:39+00:00','2026-10-14T03:11:39+00:00',5,1,'2026-10-14T03:11:39+00:00');
CREATE TABLE envoy_packages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    destination TEXT NOT NULL CHECK (destination IN ('codex', 'chatgpt', 'external')),
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'draft'
                CHECK (state IN ('draft', 'sent', 'answered', 'closed')),
    mission_id  INTEGER,
    created_at  TEXT NOT NULL,
    sent_at     TEXT,
    result_text TEXT NOT NULL DEFAULT '',
    answered_at TEXT,
    closed_at   TEXT
);
INSERT INTO envoy_packages VALUES(1,'jason','codex','Re-review PR #66 fix at 544bbf49','Independent re-review of the SQLite guard fix on branch feature/p0-2-source-health-verification-20261013: confirm the prior FAIL is resolved, the catch is appropriately bounded, and the regression test genuinely exercises the escape path.','answered',2,'2026-10-14T03:11:57+00:00','2026-10-14T03:11:58+00:00','PASS — prior FAIL resolved; catch appropriately bounded to the verifier; regression test exercises the escape; exact-head CI green on Python 3.11 and 3.13. Caveat: the test simulates the DB error rather than locking a real database.','2026-10-14T03:11:58+00:00',NULL);
INSERT INTO envoy_packages VALUES(2,'jason','codex','Final independent review: fix/narrow-guard-siblings-20261013','When the branch lands on GitHub: independently review the three narrow-guard sibling fixes (job_operations run_once tail, cloud_worker backup tick, app.py project_health branch) — one commit each, regression tests red on main and green on the branch; scrutinize the changed backup-cooldown test. DRAFT: not sent until the branch exists.','closed',NULL,'2026-10-14T03:11:58+00:00','2026-10-14T03:21:47+00:00','Codex final review of PR #74: FAIL, would not ship as-is. Main blocker: escalation dedupe uses kind+title only, so a second job''s escalation is marked sent against a request whose context carries only the first job''s evidence; the second job''s evidence is lost. Rowan independently confirmed the defect in the branch code (create_request dedupes on kind+title+open; _deliver_pending_retry_escalations marks escalation_sent against the deduplicated request id). Two related lifecycle warts also noted: dedupe checks open requests only (owner-resolved requests can duplicate across ticks); retry_job back-to-queued leaves orphan escalation_pending events. Codex made no code changes, per instructions.','2026-10-14T03:58:31+00:00','2026-10-14T03:58:31+00:00');
INSERT INTO envoy_packages VALUES(3,'jason','codex','Fix escalation dedupe defect on PR #74 branch','Fix the escalation-delivery defect Codex found in its final review of fix/narrow-guard-siblings-20261013: create_request dedupes on kind+title+open and _deliver_pending_retry_escalations marks escalation_sent against the deduplicated request, losing the second job''s evidence. Invariant: escalation_sent only when that job''s own evidence is durably attached to the request it points at. Regression tests must fail on current head and pass with the fix; full suite counts reported; exact-head CI green; same branch, new commits; no merge, no PR comment; report back in the Verify PR #66 thread.','closed',NULL,'2026-10-14T03:59:53+00:00','2026-10-14T04:01:44+00:00','Codex fixed the escalation dedupe defect in commit 26889809 on fix/narrow-guard-siblings-20261013 (PR #74). Design: create_request gained dedupe_context=True for evidence delivery — dedupe identity is kind+title+exact context, matched in any status, serialized with BEGIN IMMEDIATE; other callers unchanged. Rowan independently verified: red/green exact (3 new tests fail on 5dc00cb, pass on 26889809; targeted file 19/19); full suite 514 passed / 24 failed with failure set identical to the pre-fix branch baseline; compileall clean; diff read line by line; Codex reports exact-head CI green on Python 3.11 and 3.13 (its env: 532 passed, 6 skipped). The retry_job stale-pending-events wart was left unchanged and documented, as briefed. No merge, no PR comments.','2026-10-14T04:13:04+00:00','2026-10-14T04:13:04+00:00');
INSERT INTO envoy_packages VALUES(4,'jason','chatgpt','Design a modern Luna/ORBIT front page','Jason''s request 2026-10-14 00:06 EDT: the current UI feels like a website from the 90s; design a pleasant, modern front page where a visitor instantly understands why Luna will change their whole life. Brief: landing page for Luna/ORBIT, Moonlight identity as the starting palette, hero + sections + real draft copy, one page, for Jason''s approval.','closed',NULL,'2026-10-14T04:08:22+00:00','2026-10-14T04:12:50+00:00','ChatGPT delivered the complete one-page landing design in the ''Assess Luna ORBIT completion'' thread (2026-10-14 12:20 AM). Keeps the Moonlight identity (charcoal #121212, surface #1E1E1E, violet #9C27B0, adds brighter violet #C66BDA + soft gray #B8B4BC text; Inter typography). Hero headline: ''Give Luna the task. Get your time back—and proof it is handled.'' Eight sections: header, hero with mission-receipt visual, how a mission works, the specialist team (orbit graphic, Research/Planning/Making/Checking), memory and control, work while you are away, ORBIT and the future, closing CTA ''Meet Luna''. Honest closing note: copy is forward-looking and should reflect verified behavior at launch. Captured verbatim by Rowan to goal files/Luna-Front-Page-Design-from-ChatGPT-2026-10-14.md.','2026-10-14T04:23:49+00:00','2026-10-14T04:23:50+00:00');
INSERT INTO envoy_packages VALUES(5,'jason','codex','Rebase PR #74 branch onto merged main and force-push','Jason ordered both PRs merged. PR #66 is merged; main is now e691c50142911f365d7956e376a5c101a9924a66. PR #74 (branch fix/narrow-guard-siblings-20261013 at 26889809) conflicts with the new main in luna/job_operations.py and app.py. Rowan''s GitHub connector has no force-push, so Codex must rewrite the branch: rebase onto e691c501, resolve both files keeping BOTH changes (PR #66''s sqlite3.Error verifier guard + this branch''s escalation delivery; PR #66''s source fingerprint + this branch''s guarded health follow-ups), run compileall + full pytest, force-push with --force-with-lease, report the new head SHA + test counts. Do NOT merge; Rowan verifies the pushed tree and merges.','closed',NULL,'2026-10-14T05:53:35+00:00','2026-10-14T06:02:42+00:00','Codex rebased fix/narrow-guard-siblings-20261013 onto merged main e691c501 and force-pushed new head ee0a1e3854f6d7587507218620b9f49d9b6541ff (4 commits replayed in order). Rowan verified the pushed tree firsthand: job_operations.py carries BOTH PR #66''s sqlite3.Error verifier guard and PR #74''s escalation delivery; app.py carries BOTH the source fingerprint and the guarded health follow-ups; compileall clean; targeted tests 51/51 across the six affected files. Rowan then merged PR #74 via the GitHub connector (Jason approved the merge card): merge commit 09394e26051ed0c52dd69bed38db1c57725c2dc3 = new main HEAD. Post-merge full suite on new main: 521 passed / 24 failed, failure set byte-identical to the pristine-main baseline - zero regressions.','2026-10-14T06:15:41+00:00','2026-10-14T06:15:42+00:00');
CREATE TABLE operator_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    action      TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    classification TEXT NOT NULL DEFAULT 'routine'
                CHECK (classification IN ('routine', 'consequential')),
    outcome     TEXT NOT NULL DEFAULT 'done'
                CHECK (outcome IN ('done', 'refused')),
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
INSERT INTO operator_actions VALUES(1,'jason','db_summary','{}','routine','done','read-only DB summary','2026-10-14T03:15:05+00:00');
INSERT INTO operator_actions VALUES(2,'jason','read_file','{"path": "../luna_v2.db"}','routine','refused','path escape refused: ''../luna_v2.db'' resolves outside the Luna workspace (/home/hatch/workspace/luna-v2)','2026-10-14T03:15:05+00:00');
INSERT INTO operator_actions VALUES(3,'jason','exec','{"path": "x"}','consequential','refused','operator v1 has no consequential actions — ''exec'' is outside its scope. Such work routes to Rowan and needs Jason''s approval; Operator never writes, deletes, or executes anything.','2026-10-14T03:15:05+00:00');
INSERT INTO operator_actions VALUES(4,'jason','db_summary','{}','routine','done','read-only DB summary','2026-10-14T03:24:53+00:00');
INSERT INTO operator_actions VALUES(5,'jason','read_file','{"path": "luna_v2/__init__.py"}','routine','done','read ''luna_v2/__init__.py'' (816 chars)','2026-10-14T03:24:53+00:00');
INSERT INTO operator_actions VALUES(6,'jason','read_file','{"path": "../MEMORY.md"}','routine','refused','path escape refused: ''../MEMORY.md'' resolves outside the Luna workspace (/home/hatch/workspace/luna-v2)','2026-10-14T03:24:53+00:00');
CREATE TABLE design_proposals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    name          TEXT NOT NULL,
    tokens_json   TEXT NOT NULL,
    rationale     TEXT NOT NULL DEFAULT '',
    state         TEXT NOT NULL DEFAULT 'proposed'
                  CHECK (state IN ('proposed', 'approved', 'rejected')),
    created_at    TEXT NOT NULL,
    decided_at    TEXT,
    decided_by    TEXT NOT NULL DEFAULT ''
);
INSERT INTO design_proposals VALUES(1,'jason','Moonlight Workspace','{"background": "#121212", "surface": "#1E1E1E", "text": "#FFFFFF", "muted": "#4C5463", "accent": "#9C27B0", "accent_text": "#FFFFFF", "border": "#222222", "max_width": 1100, "roundness": 18}','Luna''s live look: dark charcoal with a violet accent, seeded as the baseline theme.','approved','2026-10-14T03:24:51+00:00','2026-10-14T03:24:51+00:00','jason');
INSERT INTO design_proposals VALUES(2,'jason','Deep Space Draft','{"background": "#0A0A1A", "surface": "#1F2A44", "text": "#FFFFFF", "muted": "#6A7C9E", "accent": "#7A5FFF", "accent_text": "#000000", "border": "#0F0F30", "max_width": 1200, "roundness": 8}','A deep‑space navy background with a lighter navy surface provides a dark, calming canvas while white text ensures strong readability, and a vivid blue‑violet accent paired with black accent text delivers crisp contrast.','rejected','2026-10-14T03:25:03+00:00','2026-10-14T03:25:03+00:00','rowan');
CREATE TABLE mentor_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    runs_graded     INTEGER NOT NULL,
    grades_json     TEXT NOT NULL DEFAULT '[]',
    suggestions_filed INTEGER NOT NULL DEFAULT 0
);
INSERT INTO mentor_reviews VALUES(1,'jason','2026-10-14T03:24:52+00:00',1,'[{"run_id": 1, "specialist": "scout", "grade": "strong", "reason": "completed cleanly", "mission_attributed": true}]',0);
CREATE TABLE builder_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    mission_id      INTEGER,
    task            TEXT NOT NULL DEFAULT '',
    target_relpath  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL CHECK (status IN ('done', 'failed')),
    proposed_content TEXT NOT NULL DEFAULT '',
    diff_text       TEXT NOT NULL DEFAULT '',
    test_exit_code  INTEGER NOT NULL DEFAULT 0,
    test_tail       TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);
INSERT INTO builder_runs VALUES(1,'jason',6,'Add a docstring to the greet function explaining what it does, and make greet strip surrounding whitespace from the name before greeting. Keep the function name and signature the same.','hello.py','done',replace('def greet(name):\n    """Return a greeting for the given name after stripping surrounding whitespace."""\n    return "Hello, " + name.strip()','\n',char(10)),replace('--- hello.py (current)\n+++ hello.py (proposed)\n@@ -1,2 +1,3 @@\n def greet(name):\n-    return "Hello, " + name\n+    """Return a greeting for the given name after stripping surrounding whitespace."""\n+    return "Hello, " + name.strip()','\n',char(10)),0,replace('----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK\n','\n',char(10)),'2026-10-14T03:25:24+00:00');
CREATE TABLE storm_state (
    owner TEXT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'normal',
    since TEXT,
    lat REAL,
    lon REAL,
    last_check_at TEXT,
    last_error TEXT
);
INSERT INTO storm_state VALUES('jason','normal',NULL,41.1475000000000008,-73.988900000000001,'2026-10-14T05:13:43+00:00',NULL);
CREATE TABLE storm_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE storm_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    path TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
DELETE FROM sqlite_sequence;
INSERT INTO sqlite_sequence VALUES('missions',6);
INSERT INTO sqlite_sequence VALUES('steps',19);
INSERT INTO sqlite_sequence VALUES('approvals',2);
INSERT INTO sqlite_sequence VALUES('receipts',6);
INSERT INTO sqlite_sequence VALUES('broker_usage',14);
INSERT INTO sqlite_sequence VALUES('broker_ledger',14);
INSERT INTO sqlite_sequence VALUES('specialist_runs',1);
INSERT INTO sqlite_sequence VALUES('verification_runs',4);
INSERT INTO sqlite_sequence VALUES('qm_reports',3);
INSERT INTO sqlite_sequence VALUES('watchman_reports',2);
INSERT INTO sqlite_sequence VALUES('sentinel_audits',1);
INSERT INTO sqlite_sequence VALUES('armorer_tools',6);
INSERT INTO sqlite_sequence VALUES('memory_entries',1);
INSERT INTO sqlite_sequence VALUES('schedules',1);
INSERT INTO sqlite_sequence VALUES('guardian_suggestions',1);
INSERT INTO sqlite_sequence VALUES('envoy_packages',5);
INSERT INTO sqlite_sequence VALUES('operator_actions',6);
INSERT INTO sqlite_sequence VALUES('design_proposals',2);
INSERT INTO sqlite_sequence VALUES('mentor_reviews',1);
INSERT INTO sqlite_sequence VALUES('builder_runs',1);
CREATE UNIQUE INDEX guardian_suggestions_open_dedupe
    ON guardian_suggestions(dedupe_key) WHERE status = 'open';
COMMIT;
