# Phase 0 Data Check

## Distinct tracking event values

- `autoevent_ballsnap`
- `autoevent_passforward`
- `autoevent_passinterrupted`
- `ball_snap`
- `dropped_pass`
- `first_contact`
- `fumble`
- `fumble_offense_recovered`
- `handoff`
- `huddle_break_offense`
- `lateral`
- `line_set`
- `man_in_motion`
- `out_of_bounds`
- `pass_arrived`
- `pass_forward`
- `pass_outcome_caught`
- `pass_outcome_incomplete`
- `pass_tipped`
- `penalty_flag`
- `play_action`
- `qb_sack`
- `qb_strip_sack`
- `run`
- `shift`
- `tackle`

## Last recorded event per play

| Last event | Play count |
|---|---|
| `pass_forward` | 6064 |
| `autoevent_passforward` | 882 |
| `run` | 448 |
| `qb_sack` | 446 |
| `pass_arrived` | 330 |
| `autoevent_passinterrupted` | 180 |
| `pass_tipped` | 80 |
| `qb_strip_sack` | 42 |
| `pass_outcome_incomplete` | 34 |
| `pass_outcome_caught` | 23 |
| `first_contact` | 17 |
| `fumble` | 4 |
| `tackle` | 3 |
| `dropped_pass` | 1 |
| `out_of_bounds` | 1 |
| `huddle_break_offense` | 1 |
| `penalty_flag` | 1 |

## Snap / end-of-dropback resolution survey

- Total plays surveyed: **8557**
- Unresolved plays: **24**

### Unresolved reasons

| Reason | Count |
|---|---|
| `no_snap_event` | 24 |

### Unresolved plays (gameId, playId, reason)

| gameId | playId | reason |
|---|---|---|
| 2021091200 | 4367 | `no_snap_event` |
| 2021091202 | 3606 | `no_snap_event` |
| 2021091206 | 1296 | `no_snap_event` |
| 2021091904 | 1614 | `no_snap_event` |
| 2021091907 | 1836 | `no_snap_event` |
| 2021091907 | 1857 | `no_snap_event` |
| 2021091909 | 3565 | `no_snap_event` |
| 2021091912 | 1868 | `no_snap_event` |
| 2021092605 | 1911 | `no_snap_event` |
| 2021092611 | 1641 | `no_snap_event` |
| 2021100302 | 775 | `no_snap_event` |
| 2021100302 | 3688 | `no_snap_event` |
| 2021100307 | 4668 | `no_snap_event` |
| 2021100308 | 4330 | `no_snap_event` |
| 2021100313 | 1878 | `no_snap_event` |
| 2021100700 | 2963 | `no_snap_event` |
| 2021101004 | 3595 | `no_snap_event` |
| 2021101004 | 3861 | `no_snap_event` |
| 2021101706 | 1932 | `no_snap_event` |
| 2021101800 | 3505 | `no_snap_event` |
| 2021102405 | 4101 | `no_snap_event` |
| 2021102408 | 1872 | `no_snap_event` |
| 2021102410 | 3833 | `no_snap_event` |
| 2021103101 | 4401 | `no_snap_event` |

## Missing-value rates

| Field | Missing rate |
|---|---|
| `pff_nflIdBlockedPlayer` | 75.29% |
| `pff_positionLinedUp` | 0.00% |
| `tracking.x` | 0.00% |
| `tracking.y` | 0.00% |
| `tracking.s` | 0.00% |
| `tracking.a` | 0.00% |
| `tracking.dis` | 0.00% |
| `tracking.o` | 4.35% |
| `tracking.dir` | 4.35% |
