# Login Tracking Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Password-protected Eww control and non-destructive recovery for encrypted login history.

**Architecture:** A dedicated system service owns storage, credentials and tracking state. The existing GTK viewer becomes a Unix-socket client. Administrator-authorized enrollment migrates the existing vault before removing verified old live copies.

**Tech Stack:** Python 3, SQLCipher 4, PyNaCl Argon2id/sealed boxes, GTK 3, systemd, Eww.

**Spec:** `docs/superpowers/specs/2026-10-31-login-tracking-control-design.md`

## Global Constraints

- Seven elapsed days of retention, local-date grouping, selected deletion only.
- New installations start Off; ordinary clients cannot enroll or bypass Off.
- Recovery code stays off this laptop; only salted hashes persist.
- Root-owned backend copies, dedicated UID, no network listener or user-owned key fallback.
- Preserve unrelated work; no commits; disposable tests under `/tmp` only.
- Camera capture retains its normal indicator. No GPIO suppression.
- Apply live when authorized system authentication permits; secrets entered locally only.

## Review Focus

1. Missing credentials with existing data must fail closed.
2. Recovery interrupted at commit must preserve history and leave a usable credential set.
3. Slow/oversized socket clients must not block expiry or consume unbounded workers.
4. Repeated setup must not overwrite keys, owner identity, credentials or state.
5. Migration failure and source changes must preserve the source, without user-owned secret backups.

### Task 1: Protected backend and storage

**Files:** `scripts/login_store.py`, `scripts/login_service.py`, temporary `/tmp/login-tracking-check.py`.

**Interfaces:** `Store(root)` handles encrypted records; `Service(root, owner)` handles validated requests with connection-scoped authentication. Requests are bounded JSON over a peer-checked Unix socket; status exposes only setup/enabled state. Authenticated operations: state, list, get, delete, recovery-code rotation. Recovery replaces verifiers and session generation atomically. Capture validates the caller's real logind session and checks Off under the same lock as toggles.

- [x] Write disposable checks for password/recovery, Off enforcement, expiry, migration and missing state; run to observe failure before backend exists.
- [x] Reuse SQLCipher and sealed-record helpers; replace camera suppression with bounded ordinary capture.
- [x] Implement private atomic credential state, Argon2id verification, protected rate limiting, root-only enrollment and serialized operations.
- [x] Run backend checks against real SQLCipher and socket requests. Expected: encrypted file, authenticated queries only, recovery preserves records/keys/state and revokes old sessions/code.

### Task 2: Client and Eww

**Files:** `scripts/login_log.py`, `scripts/desktop-controls.py`, `eww/eww.yuck`, `eww/scripts/qs.sh`.

**Interfaces:** `Client.request(op, **fields)` returns validated service responses; GTK dialogs collect secrets locally. Viewer fetches metadata separately from selected photos. Setup uses a fixed root-owned admin helper; recovery returns a new code only to the local dialog.

- [x] Write disposable client checks for framing/error handling, canceled dialogs and failed authentication.
- [x] Preserve date grouping/search/delete confirmation; add password/recovery dialogs, replacement-code action and toggle.
- [x] Add status-only Eww fields and detached dialog launch, following existing row styling.
- [x] Run isolated GTK checks and validate Eww load. Expected: cancellation leaves state unchanged; no secrets in Eww or arguments.

### Task 3: Installation, migration and live application

**Files:** `setup/login_tracking.py`, `setup/login_tracking_install.py`, `setup/login_tracking_admin.py`, `setup/systemd/i3-login-log.*`, `setup/main.py`, manifests, old user units, `docs/productivity.md`.

**Interfaces:** `install(run)` installs fixed root-owned files and invokes the root-owned installer; `check()` reports service/setup differences without mutation. Installer fixes owner UID, stages verified legacy files, and enables the protected service. Admin helper permits enrollment only and removes unchanged source copies only after successful verification.

- [x] Exercise installation in a disposable root with mocked system commands, twice; assert no overwrite of state/keys/identity and no privileged symlinks.
- [x] Wire native SQLCipher dependencies, service hardening, cleanup and repeatable `setup.sh apply` route. Remove obsolete user capture/prune units.
- [x] Document password/recovery flow and actual security limits under docs, leaving README compact.
- [x] Run syntax, service verification, focused setup checks and full disposable regression checks. Apply live without desktop restart. If local administrator authentication or vault password is required, open the local setup flow and report its pending state honestly.
- [x] Obtain one fresh final review, fix material findings with reproducing checks, remove disposable test artifacts.

## Verification record

Completed 2026-10-31. Disposable checks covered native SQLCipher encryption,
password/recovery verification, atomic state interruption, session revocation,
seven-day record/dedup expiry while Off, capture/toggle serialization, legacy
migration, changed-source cleanup, socket framing/deadlines/peer credentials,
GTK cancellation/grouping/photo/delete flows, and isolated Eww flyout loading.
Installer fresh/repeat runs were simulated with disposable files and mocked system
commands; a full fresh-machine VM was not run. Independent final review found and
verified fixes for migration source cleanup, dedup expiry and slow socket framing.

Applied live: native APT dependencies, dedicated service UID, root-owned code and
systemd units, Eww reload, local administrator enrollment/migration. Focused setup
check reports no differences; ordinary desktop UID cannot open protected storage;
old live database/key/vault copies were removed after destination verification.
Tracking remains Off. Fresh login and real camera capture under the new service
were not exercised; the normal camera indicator is retained.

Execution decisions: used the existing dirty checkout to preserve ongoing work;
no commits or pushes. Dedup identifiers expire with the seven-day history, so a
session lasting longer than seven days can record again if its startup hook is
explicitly invoked after expiry. Camera indicator suppression is excluded.
