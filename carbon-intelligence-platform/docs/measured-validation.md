# Real power validation protocol

## Current status

The live power model currently uses synthetic, formula-generated target values. Its existing metrics describe fit to that synthetic generator and do not establish accuracy on this computer. Wall-input validation is **not yet performed** because no plug-in power meter readings are available.

The power-reading workflow below supports an external meter and HWiNFO's CPU Package Power or Total System Power sensors. Candidate models are saved separately and are not activated by the app automatically. CPU Package Power is CPU-domain only. HWiNFO Total System Power is a platform-reported estimate, not an external wall-input measurement.

## Use HWiNFO CPU Package Power (no external meter)

These are useful free signals available in the current HWiNFO captures. Prefer **Total System Power** when it is present and logged; otherwise use **CPU Package Power** for a CPU-only experiment. Neither sensor is an external AC wall-power measurement.

1. In HWiNFO Sensors, enable CSV logging and ensure the log includes **Date**, **Time**, and **Total System Power [W]** if available, plus **CPU Package Power [W]**. Keep the HWiNFO log interval at or near the app's telemetry interval (5 seconds by default); shorter intervals are also fine.
2. Start the Carbon Intelligence app, then click **Start Session**. Keep that session active for the complete workload and HWiNFO capture. The app writes matching session-tagged telemetry to `data/measured/telemetry_YYYYMMDD.csv`.
3. In PowerShell, obtain the active session ID:

   ```powershell
   (Invoke-RestMethod http://127.0.0.1:5000/api/session/current).session.session_id
   ```

   If no session is active, start one in the dashboard first. Use a new app session ID for every independent workload repeat.
4. Stop HWiNFO logging, then convert its raw CSV. Replace the example paths and session ID with your actual values:

   ```powershell
   python -m app.ml.import_hwinfo `
     --input "C:\Users\YOUR_NAME\Documents\hwinfo-log.csv" `
     --output data/measured/cpu_power_run1.csv `
     --session-id YOUR_SESSION_ID `
     --workload cpu_load `
     --target-sensor cpu-package-power `
     --timezone Asia/Kolkata
   ```

   This imports CPU Package Power. To import the broader HWiNFO platform sensor instead, set `--target-sensor total-system-power` and use a correspondingly named output file. The importer turns local HWiNFO timestamps into UTC. If it reports an ambiguous sensor column, pass its exact header using `--power-column "<header>"`. For another timezone, change `--timezone` to its IANA name.
5. Align the imported readings with that date's app telemetry:

   ```powershell
   python -m app.ml.measured_dataset `
     --telemetry data/measured/telemetry_YYYYMMDD.csv `
     --power-readings data/measured/cpu_power_run1.csv `
     --tolerance-seconds 2.5 `
     --output data/processed/power_reading_training.csv
   ```

6. Repeat across separate sessions. Once at least three distinct sessions align, evaluate a candidate:

   ```powershell
   python -m app.ml.evaluate_measured `
     --input data/processed/power_reading_training.csv `
     --report reports/power_reading_evaluation.json `
     --candidate-dir models/power_reading_candidate `
     --plot-dir reports/power_reading_figures
   ```

   The report records which HWiNFO target was evaluated. Its candidate is not activated in the live app. Do not combine CPU Package Power and Total System Power rows in one training set. Three sessions only allow a minimal split; aim for at least five independent repeats per workload, with longer captures, before interpreting accuracy.

## Measurement setup

1. Use a plug-in power meter or smart plug that records active power in watts and can export timestamped readings. Record only the computer in the meter's measurement scope; disconnect or exclude the display and other devices if the research question is computer-only.
2. Use one machine for the first experiment. Record a non-identifying hardware description (CPU, memory, GPU if available, and OS version) and the meter make/model. Do not record serial numbers or account names.
3. Restart the Carbon Intelligence app with the updated code and run it at its configured telemetry interval. During each active app session it stores session-tagged snapshots in daily files under `data/measured/telemetry_YYYYMMDD.csv`. This separate capture avoids changing the historic general telemetry logs.
4. Start one app session for each workload repeat and use that app's exact `session_id` on every corresponding power-meter row. You can obtain the ID from `GET /api/session/current` while it is active, or from session history after stopping. Record workload labels such as `idle`, `browser`, `coding`, and `heavy_workload`. Use multiple sessions per workload and allow the machine to settle before each recorded segment.
5. Export meter data into `data/measured/`. Use the header in `data/templates/power_meter_readings_template.csv`. Required fields are `timestamp`, `power_w`, and `session_id`. Timestamps must include their timezone offset; UTC (`Z`) is preferred. Keep the meter's raw export unchanged as a source record.
6. Document what the meter includes in `measurement_scope`, such as `wall_input_computer_only`. Wall input includes power-supply conversion losses and is not the same as component DC power.

## Align the two data sources

The app telemetry CSV and meter export are joined to the nearest timestamp within a strict tolerance. Rows outside tolerance are discarded and counted. Alignment never crosses session IDs.

```powershell
python -m app.ml.measured_dataset `
  --telemetry data/measured/telemetry_YYYYMMDD.csv `
  --power-readings data/measured/power_readings.csv `
  --tolerance-seconds 2.5 `
  --output data/processed/measured_training_data.csv
```

Inspect the match counts printed in the terminal and verify sample times and meter units before training. Do not widen the tolerance just to increase the row count; investigate clock offsets and sampling gaps first.

## Evaluate without session leakage

```powershell
python -m app.ml.evaluate_measured `
  --input data/processed/measured_training_data.csv `
  --report reports/measured_evaluation.json
```

Evaluation groups by `session_id`, so complete sessions are held out together. It uses separate training, validation, and untouched final-test sessions. The validation sessions choose among a median baseline, Linear Regression, Random Forest, and Gradient Boosting; a regression model is selected only if it beats the median baseline on validation RMSE. Final-test MAE, RMSE, R², and workload-specific metrics are reported for review. Features entirely unavailable in training sessions are excluded rather than filled with fabricated measurements.

If a regression model beats the baseline on validation, its pipeline is saved under `models/measured_candidate/` for review. If no candidate beats the baseline, the report says not to deploy one. Any candidate is deliberately **not the live model**. Only consider deployment after checking the final held-out session metrics, workload errors, timestamp alignment, measurement scope, and residual plots. These results initially apply only to the measured machine and workloads; testing generalization requires additional hardware.

## Minimum useful experiment

Aim for at least 5 independent sessions per workload, with several minutes per session and repeat runs on different occasions. More sessions are preferable. Keep complete sessions separated for training, validation, and final testing. Report the number of sessions in each split, row match rate, meter scope, workload mix, and limitations alongside every metric.

