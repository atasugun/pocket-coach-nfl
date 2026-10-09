# Level 2 Calibration

Thresholds tuned on the training split (100 games); precision/recall below is computed on the held-out split only (22 games).

| Rule | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| `free_rusher` | 12.5% | 1.2% | 8 | 56 | 664 |
| `lost_escape_lane` | no answer key | no answer key | — | — | 15 flags, manual review |
| `stunt_not_handled` | 73.9% | 9.7% | 65 | 23 | 607 |
| `wasted_double_team` | 21.4% | 4.9% | 33 | 121 | 639 |

`lost_escape_lane` has no PFF label that can confirm a defensive containment breakdown, so it is validated by manual review of a sample of flagged plays instead of against PFF labels (Requirement 6.8).