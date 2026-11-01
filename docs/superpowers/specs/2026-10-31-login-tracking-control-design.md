# Login tracking controls and recovery

Status: approved for implementation.

## Intent

Thomas wants an Eww toggle that controls future i3 login captures. Changing the
toggle requires his own application password. The history stays encrypted, grouped
by local date/time, searchable in Login History, and expires after seven days.
Forgotten-password recovery must preserve history and must not become a shortcut
for someone to disable tracking, read records, or erase their footprint.

Thomas selected a recovery code kept off this laptop as the recovery credential.

## Initial enrollment

Initial password/recovery enrollment and legacy migration require an
administrator-authorized setup action. An uninitialized service remains Off and
returns Setup required to normal clients; it must never let the first ordinary
user process claim ownership. Fix the permitted desktop account during this
administrator-controlled bootstrap. Enter all secrets locally, without arguments,
environment variables, terminal history/scrollback, or diagnostic output.

After enrollment, repeat setup preserves credentials. Missing/damaged credential
files with existing protected data must fail closed, not reopen enrollment or
replace keys. Normal password recovery uses the recovery code and does not
require administrator access. The installer cannot silently overwrite an
initialized vault.

## Approach

Use a protected local system service with a dedicated system account. It owns the
database, encryption keys, password hash, recovery-code hash, and tracking state.
The Eww control and viewer are clients. The application password authenticates
requests; it is separate from the encryption keys.

Alternatives considered:

- A password check and key in Thomas's home directory cannot enforce this boundary
  against another application running as Thomas.
- Administrator-password recovery is possible but Thomas chose an independent,
  off-laptop recovery code instead.
- A password-encrypted private key alone protects locked content, but changing a
  password hash cannot recover that key after the password is forgotten.

## Controls

- Add a Login tracking row to Eww's existing Controls panel, matching its current
  styling. Show On, Off, or Unavailable. Eww receives status only, never secrets.
- Require the application password for either toggle direction. Canceling or
  failing authentication leaves the previous state unchanged.
- Off means no new login metadata or photos. Existing records remain available
  after authentication and continue to expire normally. On resumes at the next
  i3 login; enabling does not retroactively capture activity.
- Persist the state in the protected service, across login and reboot. Proposed
  initial state for new installations: Off until explicitly enabled.
- Viewing and deleting selected records remain authenticated operations. Keep the
  existing confirmation before deleting a selected record. No clear-all or
  unauthenticated destructive reset is part of recovery.

## Recovery

1. At setup, generate a high-entropy random recovery code and display it locally
   once. Thomas saves it off the laptop. Do not write it to chat, clipboard,
   command arguments, environment variables, diagnostics, or a local recovery file.
2. Store only salted Argon2id verifiers for the access password and recovery code
   in the protected service's private directory. Never store the access password.
3. Forgot password requests the recovery code before allowing a new password.
   The protected service verifies the code; the client cannot authorize itself.
4. Successful recovery replaces the password verifier and recovery code, invalidates
   existing authenticated sessions, and presents a new recovery code to save.
5. Recovery preserves every unexpired record, the encryption keys, and the On/Off
   state. It never deletes or recreates the database.
6. Wrong codes and canceled recovery change neither history nor credentials nor
   tracking state. Rate-limit attempts in protected state; avoid a permanent
   lockout that someone else could use to deny the owner access.
7. Losing both the password and recovery code provides no unauthenticated reset
   or erase option. A system administrator remains outside this application's
   security boundary; the app must not pretend it can prevent root overrides.

Recovery credential rotation must commit atomically. If the new code was not
saved or a setup/recovery window closes unexpectedly, authenticated access must
still offer a way to issue a replacement code without wiping history.

## Service and key boundary

- Install trusted backend code and system units as root-owned copies through
  setup. Never run privileged code through a symlink into the user-writable repo.
- Keep private data under `/var/lib/i3-login-log`, owned by the dedicated service
  account, with private directories/files. Normal user applications cannot read
  keys, change password verifiers, or edit the tracking flag directly.
- Use a local Unix socket, restricted to the configured desktop account, with
  peer-credential checks and bounded validated requests. No network listener.
- Require server-side authentication for record access, deletion, state changes,
  and recovery. Scope authenticated sessions to the client connection, expire them
  after inactivity, and invalidate them after recovery. Never cache passwords in
  Eww variables or send them in process arguments.
- Keep SQLCipher encryption and the existing encrypted record contents. The
  service holds the required keys independently of the access-password verifier,
  so a verifier reset does not make records unreadable.
- Automatic login capture needs no password prompt. The existing i3 startup hook
  requests capture; the service checks On/Off itself and deduplicates the actual
  user/session identity before capturing. A direct client call cannot override Off.
- Keep machine-specific camera settings out of Git. Capture uses the normal
  camera activity indicator; the application does not suppress the LED.
- Continue seven-day expiry even while tracking is Off. Cleanup must not require
  the application password or expose decrypted content to the desktop user.

This protects stored keys and service controls from ordinary user applications.
It is not a guarantee against root compromise, a compromised backend, or malware
observing input/windows in this i3/X11 session. A user-owned i3 startup hook can
also be disabled; this feature is not an unskippable OS login audit. Filesystem
snapshots, old backups, and already-decrypted copies cannot be revoked by the app.

## Migration and setup

Preserve current encrypted history and the existing private vault. Migration needs
the current vault password once, entered locally, to transfer its key material to
the service. Verify the destination before removing old user-readable live copies.
Do not use a user-owned backup folder for privileged key material. If unlocking or
migration fails, retain the source and do not silently replace its keys or records.

Setup must install dependencies, the service account, root-owned backend/units,
local camera configuration, socket permissions, Eww control, and cleanup. Repeat
installation preserves history, credentials, recovery state, and tracking state.
Document the initial password/recovery-code step and any administrator action in
`docs/`; README receives only a compact usage pointer if needed.

## Verification before release

Use disposable service/data fixtures to verify correct/wrong password and code,
toggle cancellation and persistence, direct-request enforcement of Off, concurrent
capture/control changes, and seven-day expiry while Off. Verify recovery preserves
record contents and keys, keeps tracking state, revokes old codes/sessions, and
survives interruption without data loss. Verify failed recovery cannot delete data.

Test that the desktop user cannot read or overwrite protected files, that the
service does not return keys, and that secret values stay out of logs/arguments.
Check the Eww and viewer flows on an isolated display, repeat setup in isolation,
and then apply live. Verify live capture without restarting
the desktop. Report fresh-login/hardware checks that still require observation.
