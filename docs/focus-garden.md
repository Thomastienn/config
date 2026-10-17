# Focus Garden

Open **Focus** in Polybar or press **Super+Ctrl+F**. The popup is an i3 floating
window: use Tab/Shift+Tab and Enter/Space, its close button, the same shortcut, or
Super+Q. Closing it leaves the timer running. No application is opened or closed;
[lock-in](#lock-in) only hides distracting windows during a focus session.

The window uses larger text and controls, with three direct pages: **Focus** for
the current session, **Progress** for weekly activity and recent wins, and
**Notes & reminder** for parked thoughts and reminder settings. There are no
collapsed sections. It fits the display; each page scrolls when needed.

## A small loop

1. Choose **Study** or **Coding**, then **5**, **10**, or **25 minutes**. A concrete
   next action is required; each track remembers its own. Open the work windows
   and signed-in browser pages you will need before starting.
2. In Rofi, check every work window and exact Brave page you need. Click a row or
   press Shift+Enter to check/uncheck it, then click **Start with selected resources**
   or press Enter. Multiple pages and windows can be selected together. Cancelling
   changes nothing. The timer starts only after the paired browser extension
   acknowledges enforcement.
3. Work within those resources. Every five minutes before the session ends, Rofi
   asks for a short typed check-in. Study asks for one recalled idea; Coding asks
   for a concrete change or next action. Type `/stuck` to choose a smaller step.
4. At the end, see credited time and garden growth. Optional wins, saved next
   steps, and five-minute breaks remain available. Closing Focus leaves the
   session running. No completion sound is played.

## Lock-in

The guard runs only during focus sessions; breaks have no restrictions.

- **Chosen resources:** selected desktop windows stay approved even when their
  filenames change. Their file/save dialogs are allowed too. Work apps, AI chats,
  educational pages, and remembered classifications are not automatic exceptions.
  Rofi, Focus, audio controls, and authentication dialogs remain usable.
- **Exact pages:** approval includes the path and query string. Different YouTube
  video IDs, searches, and SPA routes require new access. Normal `#section`
  anchors remain allowed; `#/` and `#!/` application routes are checked separately.
  The extension blocks unapproved top-level HTTP(S) navigation across normal
  windows of the paired Brave profile. Already-loaded tabs open an approval gate
  without closing or reloading the original tab. Unapproved tabs are temporarily
  muted; only mute changes owned by the extension are restored.
- **Fast return:** an unapproved desktop window stops earning time immediately.
  After two seconds it moves to the scratchpad, returning focus to approved work.
  Reopening or rapidly switching windows does not erase drift. Known distraction
  apps are hidden at the start unless deliberately selected as work.
  Paired Brave windows stay in their existing tiled/floating layout while the
  extension gates pages. A page-title update pauses credit until browser state
  catches up, without moving the browser into the scratchpad.
- **New access:** use the browser gate's **Request 5 minutes** button, or Focus's
  **Request 5 minutes for hidden window**. Type a task-related reason, then wait
  ten seconds while 9router reviews the task, resource, and reason. Relevant requests
  receive five minutes; unrelated requests stay blocked with an explanation.
  A failed, invalid, or late review grants nothing; return to chosen work or retry.
  Cancelling discards the request, including any later model reply. There are
  no permanent click-through exceptions. Other browser profiles and other browsers
  are not supported work resources; use the paired Brave profile. For local PDFs,
  choose a desktop viewer window. Sign-in redirects also need approval, so sign
  in before starting when possible.
- **Check-ins:** the prompt takes keyboard focus. Esc dismisses it but leaves
  credit paused; **Answer check-in** in Focus opens it again. Replies stay in
  memory and are discarded after handling. Responses are not graded, and the
  guard cannot verify thoughts or understanding. A new checkpoint is scheduled
  five minutes after answering. The countdown continues during pauses.
- **Ending:** **End session** asks for a reason and waits ten seconds; Focus's
  **Cancel wait & return** cancels an approval/end wait. **Emergency end** in Focus
  or the browser gate, **Super+Ctrl+Shift+F**, or **Alt+Escape** in a Rofi prompt
  ends immediately. Sleep, sign-out, and session completion also clean up.
- **Recovery:** loss of the guard, i3, browser bridge, or extension ends the
  session with only accounted time credited. Browser restrictions are removed;
  hidden tiled windows return to their workspaces. Floating/dropdown windows
  stay in the scratchpad, where they normally live. A browser worker restart
  finishes the session rather than resuming unacknowledged restrictions.
  A tiled window shown manually from the scratchpad is restored to tiling too.
- **Models:** Decima classifies content locally for feedback. 9router checks task
  relevance for new requests during the ten-second wait; genre or an educational
  label alone cannot grant access. A missing local model does not remove enforcement.
  Old remembered verdicts cannot grant access. Initial chosen resources remain approved
  for the session without a remote review.
- **Voice:** one background request to 9router supplies varied session themes,
  reflections, notifications, and bloom/milestone wording. Recent used lines
  discourage repeats; built-in alternatives work offline. Generated writing
  never controls access or awards progress.

Drift and time waiting on prompts/controls are kept separate and excluded from
plant growth. Credit uses measured intervals rather than mouse activity. A quiet
reading window still reaches its scheduled checkpoint. Five minutes is a practical
starting cadence, not an established optimum or a guarantee against zoning out.

### Install the Brave extension once

1. Run `./setup.sh apply --configs-only` (full `apply` on a fresh machine). Setup
   links the native host and registers only this extension's stable ID, preserving
   unrelated Brave configuration. Python, Rofi, Brave, and the local model are
   already covered by the normal installation route.
2. Open `brave://extensions`, enable **Developer mode**, choose **Load unpacked**,
   and select `~/thomas_config/brave/focus-guard`. Pin it, then click its toolbar
   icon to connect. This uses the existing profile; no profile data is copied.
3. Reload Eww and i3 configuration when convenient for the new controls and
   emergency shortcut. Setup does not restart the desktop. Reload the unpacked
   extension after pulling updates to its files.

If pairing is unavailable, starting Lock In reports the installation step; it
never silently starts a weaker session. Only one normal Brave profile is paired
at a time. No incognito support, site-wide research passes, or phone blocking is
included. This is a self-commitment aid, not protection against deliberate bypass.
The toolbar page shows whether its desktop connection is available. Clicking the
extension alone does not start blocking: start Lock In from Focus Garden and select
your work resources first. **Connected** with no active session is normal.

The browser bridge uses native messaging and a user-only Unix socket, with no
HTTP listener. 9router receives the original track/next action and recent generated
wording for voice. For each new access request, it also receives the resource title,
app name, page hostname/path (without query, fragment, or credentials), and typed
approval reason, forwarding these to its configured provider. Check-in replies,
smaller steps, page contents, and the full selected resource list are not sent.
Approval request text is not written to history; provider retention is separate.
Replies and resource lists are not added to Git. Full URLs and selected windows
exist only in private runtime state; check-in text is not retained. Classified titles
and generated-line history remain in the private `focus-verdicts.json` and
`focus-voice.json` state files.

Your plant grows one stage per **10 accumulated focus minutes**, blooming at
**50 minutes**. Small partial sessions carry forward, including seconds. A bloom
stays visible until your next session; completed plants stay in your collection.
Break time earns no growth. The three milestones celebrate your first five
minutes, first bloom, and first three-day week.

**Five accumulated minutes** qualifies a day. The weekly aim is **three days**,
Monday through Sunday. Dots show activity neutrally: missed days remove nothing
from your plants or total minutes. The collection also shows Study/Coding totals
and your ten most recent sessions and wins. Parked thoughts remain until cleared;
both panels show the latest twenty.

## Optional reminder

Open **Notes & reminder**, choose days such as `Mon,Wed,Fri`, then a local
24-hour time such as `18:30`. Setup leaves this disabled. The panel can change or
disable it later. An ordinary, silent notification appears at most once that day.
It skips focus sessions, breaks, a locked session, manual Do Not Disturb, and days
with at least five recorded minutes. Missed reminders are not replayed after login
or at a later clock minute. An unavailable lock/DND check also suppresses it.

The schedule is a private systemd user timer drop-in under
`~/.config/systemd/user/thomas-focus-reminder.timer.d/`. Repository units are linked
by the normal setup path. `./setup.sh apply --configs-only` applies new units on an
existing machine; it does not enable the reminder or overwrite your schedule.
On a fresh machine, opt in again from the panel.

## Storage and timer behavior

Records, wins, track choices, next steps, milestones, and reminder preferences live
in `~/.local/state/thomas-desktop/focus-garden.json` (or `$XDG_STATE_HOME`). The file
is private to your user, stored locally without encryption, and never synchronized
by this feature. Parked thoughts keep their existing `focus-notes.json` file.
Atomic replacement and a file lock protect edits; session IDs prevent duplicate
cleanup from awarding twice. Malformed garden data raises an error and stays intact.
Back it up before repairing it; the panel reports its location.

Time uses a monotonic clock, is capped at the selected duration, and belongs to the
session's starting local date. Stop, sleep, or display-session exit finalizes the
measured portion. Notification state is restored even if recording progress fails.
Manual changes to Dunst's pause level during a session are preserved. An unexpected
reboot retains completed records but does not invent credit for an unfinished timer.
Timer time is a record of the session, not a measurement of attention or learning.

There is no garden polling daemon, continuous animation, or background sync.
The guard sleeps until an i3/browser event, a prompt response, or its next deadline.
The browser owns a small native host while its extension is connected; the host
waits on messages without periodic polling. Decima loads for approval feedback
when needed and unloads after five minutes without a new title. Full setup installs
its pinned environment in `~/.virtualenvs/focus-guard` and model in
`~/.local/share/thomas-desktop/decima-small`. Polybar uses IPC. The running session
updates its clock once a second; the popup's lightweight clock runs only while an
active timer is visible. Garden/history refresh on opening or a change. Picom and
the desktop appearance keep their existing settings.

## Research and design decisions

These studies informed individual choices. They do not validate this particular
combination, guarantee improved grades, or establish a dopamine increase. Session
lengths, growth thresholds, and the three-day aim are practical defaults.

- **Make returning pleasant.** Woolley, Giurge, and Fishbach's studies connect
  intrinsic enjoyment with persistence, including longitudinal and intervention
  evidence. The garden supplies a small, predictable sign of progress alongside
  the activity itself. [Woolley et al., 2025](https://knowledge.uchicago.edu/records/0mq7t-kax65).
- **Keep control with the learner.** A meta-analysis of student motivation supports
  the relevance of autonomy and competence. Short starts, an immediate emergency exit, and
  preserving earned progress retain choice. Required checkpoints and ten-second
  approval/end waits are deliberate commitment settings, not findings of this study.
  [Bureau et al., 2022](https://doi.org/10.3102/00346543211042426).
- **Show accumulated progress.** A meta-analysis of 138 randomized studies found
  that interventions promoting progress monitoring improved goal attainment on
  average. Visible minutes and weekly dots apply that principle; plant artwork is
  our design inference. [Harkin et al., 2016](https://pubmed.ncbi.nlm.nih.gov/26479070/).
- **Give starting a cue.** Implementation-intention research supports specifying
  when and how to act. A chosen reminder and concrete next action can support an
  "at this time, I open this task" plan; an alert alone is not a full intervention.
  [Gollwitzer & Sheeran, 2006](https://doi.org/10.1016/S0065-2601(06)38002-1).
- **Leave a return path.** Ready-to-resume planning reduced attention residue in
  four interruption studies. Saving the next tiny step adapts that idea to study
  and coding. [Leroy & Glomb, 2018](https://doi.org/10.1287/orsc.2017.1184).
- **Allow imperfect weeks.** Habit formation varied substantially in a real-world
  health-routine study, and one missed opportunity did not materially derail the
  process. That does not establish a study-habit timetable. Streak-framing studies
  also show that intact/broken logs can influence engagement. We use weekly
  activity without resetting earned progress. [Lally et al., 2010](https://doi.org/10.1002/ejsp.674),
  [Silverman & Barasch, 2023](https://doi.org/10.1093/jcr/ucac029).
- **Make the win relevant to learning.** A classroom meta-analysis of 222 studies
  found benefits from quizzing/retrieval practice. The Study prompts encourage
  recall rather than treating timer completion as proof of understanding; checking
  course notes afterwards remains the learner's responsibility. It is not a
  spaced-repetition system.
  [Yang et al., 2021](https://pubmed.ncbi.nlm.nih.gov/33683913/).
- **Offer rest without promises.** A microbreak meta-analysis found small benefits
  for vigor and fatigue; the overall performance effect was not significant.
  Breaks stay optional. [Albulescu et al., 2022](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272460).
- **Keep game elements light.** Educational gamification has promising but variable
  effects, with less stable motivational findings in more rigorous subsets. Plants
  and milestones are feedback, with no random prizes, rankings, or escalating
  obligations. [Sailer & Homner, 2020](https://link.springer.com/article/10.1007/s10648-019-09498-w).
