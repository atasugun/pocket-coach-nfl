# Level 3 Models

## Pressure-probability model

- Held-out AUC: **0.696**
- Possible flags (pressure spikes) on held-out games: 600
- Calibration (predicted probability bucket -> observed pressure rate):

| Predicted bucket | Observed rate | n |
|---|---|---|
| 0.0-0.2 | 12.2% | 927 |
| 0.2-0.4 | 32.2% | 30984 |
| 0.4-0.6 | 48.1% | 12069 |
| 0.6-0.8 | 69.9% | 3172 |
| 0.8-1.0 | 91.9% | 4066 |

Frame-level features (min rusher-to-QB distance, rushers within free_rusher_qb_yd, pocket area, elapsed time, rusher/blocker counts) are labeled with the play's overall PFF hit/hurry/sack outcome broadcast to every frame — the tracking data has no frame-level pressure label, so this is a known simplification.

## Expected-rep model (depth conceded at 1.5s)

- Baseline (situational averages) MAE: **0.748 yd**
- LightGBM MAE: **0.657 yd**
- Held-out reps: 7581; Possible flags (worse than expected): 211
