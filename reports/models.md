# Level 3 Models

## Pressure-probability model

- Held-out AUC: **0.697**
- Possible flags (pressure spikes) on held-out games: 600
- Calibration (predicted probability bucket -> observed pressure rate):

| Predicted bucket | Observed rate | n |
|---|---|---|
| 0.0-0.2 | 11.7% | 945 |
| 0.2-0.4 | 32.2% | 30805 |
| 0.4-0.6 | 48.1% | 12306 |
| 0.6-0.8 | 69.7% | 3092 |
| 0.8-1.0 | 92.0% | 4070 |

Frame-level features (min rusher-to-QB distance, rushers within free_rusher_qb_yd, pocket area, elapsed time, rusher/blocker counts) are labeled with the play's overall PFF hit/hurry/sack outcome broadcast to every frame — the tracking data has no frame-level pressure label, so this is a known simplification.

## Expected-rep model (depth conceded at 1.5s)

- Baseline (situational averages) MAE: **0.748 yd**
- LightGBM MAE: **0.657 yd**
- Held-out reps: 7581; Possible flags (worse than expected): 211
