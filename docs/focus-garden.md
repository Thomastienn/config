# Focus Garden

Open **Focus** in Polybar or press **Super+Ctrl+F**. The popup is an i3 floating
window: use Tab/Shift+Tab and Enter/Space, its close button, the same shortcut, or
Super+Q. Closing it leaves the timer running. No application is opened or closed
automatically when a session ends.

The window uses larger text and controls, with three direct pages: **Focus** for
the current session, **Progress** for weekly activity and recent wins, and
**Notes & reminder** for parked thoughts and reminder settings. There are no
collapsed sections. It fits the display; each page scrolls when needed.

## A small loop

1. Choose **Study** or **Coding**. Each remembers a separate next action. Editing
   it uses Rofi and is optional; the session buttons start immediately.
2. Start **5**, **10** (the default), or **25 minutes**. Routine notifications pause.
   Park distracting thoughts for later, or stop and save measured time anytime.
3. At the end, see time saved and garden growth. If the popup is closed, one
   notification gives the result. There is no completion sound or surprise modal.
4. Optionally keep a small win, leave your next step, continue, or take a five-minute
   break. Study suggests explaining one idea from memory and then checking notes;
   Coding asks what changed or what you learned. Rewards never require an answer.

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

There is no garden daemon, idle focus poll, continuous animation, or background
sync. Polybar uses IPC, with a one-time state hook on restart. The running session
updates its clock once a second; the popup's lightweight clock runs only while an
active timer is visible. Garden/history are recalculated on opening or a change.
Picom and the desktop appearance keep their existing settings.

## Research and design decisions

These studies informed individual choices. They do not validate this particular
combination, guarantee improved grades, or establish a dopamine increase. Session
lengths, growth thresholds, and the three-day aim are practical defaults.

- **Make returning pleasant.** Woolley, Giurge, and Fishbach's studies connect
  intrinsic enjoyment with persistence, including longitudinal and intervention
  evidence. The garden supplies a small, predictable sign of progress alongside
  the activity itself. [Woolley et al., 2025](https://knowledge.uchicago.edu/records/0mq7t-kax65).
- **Keep control with the learner.** A meta-analysis of student motivation supports
  the relevance of autonomy and competence. Short starts, optional prompts, and
  stopping without loss preserve choice. [Bureau et al., 2022](https://doi.org/10.3102/00346543211042426).
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
  found benefits from quizzing/retrieval practice. The optional Study check-in
  encourages recall followed by checking, rather than treating timer completion
  as proof of understanding. It is not a spaced-repetition system.
  [Yang et al., 2021](https://pubmed.ncbi.nlm.nih.gov/33683913/).
- **Offer rest without promises.** A microbreak meta-analysis found small benefits
  for vigor and fatigue; the overall performance effect was not significant.
  Breaks stay optional. [Albulescu et al., 2022](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272460).
- **Keep game elements light.** Educational gamification has promising but variable
  effects, with less stable motivational findings in more rigorous subsets. Plants
  and milestones are feedback, with no random prizes, rankings, or escalating
  obligations. [Sailer & Homner, 2020](https://link.springer.com/article/10.1007/s10648-019-09498-w).
