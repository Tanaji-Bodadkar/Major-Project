# Dataset provenance and validation

## Dataset currently used by the application

`data/processed/training_data.csv` is generated locally by `notebooks/generate_training_data.py` (5,000 rows, seed 42). It is synthetic/model-generated data. No electrical meter, computer, benchmark run, or recorded system telemetry contributes to these rows. In particular, the CSV column `measured_power_w` is a legacy and inaccurate name: its values are modeled watts, not measured power.

The generator samples feature values from chosen distributions, then computes its target as a fixed 45 W baseline plus hand-selected CPU, RAM, disk, network and GPU contributions, with a CPU exponent of 0.62 and Gaussian noise (σ=2.5 W). The constants are not fitted from raw SPECpower observations. The generator's output is suitable only to exercise the prototype training and application code. Held-out metrics quantify reproduction of that generator and must not be presented as evidence of real-world prediction accuracy. The shuffled row order has no time information.

The code's nine feature columns and units are:

| Feature | Unit | Generator/live meaning |
|---|---|---|
| `cpu_utilization_pct` | % | Total CPU utilization |
| `cpu_frequency_mhz` | MHz | Current frequency |
| `ram_utilization_pct` | % | Memory utilization |
| `ram_used_mb` | MB | Used physical memory |
| `disk_read_mb_s`, `disk_write_mb_s` | MB/s | Read and write rates |
| `network_sent_mb_s`, `network_recv_mb_s` | MB/s | Send and receive rates |
| `gpu_utilization_pct` | % | GPU utilization; generated data conflates zero activity with no GPU |

The target column is `measured_power_w` (W) for compatibility with existing code, but its values are synthetic modeled targets. Rename it in a future dataset schema migration; do not describe it as measured.

## Candidate measured datasets investigated (10 October 2026)

### SWEAT

The [SWEAT Dataset record on Zenodo](https://zenodo.org/records/20181490) (DOI `10.5281/zenodo.20181490`) identifies a 2026 dataset from Nguyen, Noureddine and Pham, associated with *SWEAT: Software Workload Classification Across Infrastructures* (IFIP ICTSS 2026). Its record describes five server infrastructures and CPU, memory and disk benchmark configurations, with 30 runs per configuration. Its published processed schema lists CPU summary statistics, CPU frequency in GHz, memory use in GB, disk operation counts, and `energy_util_during_interval_j` in joules per 1-second interval. It describes resampling to 1-second intervals and summing energy observations over each interval.

The record describes energy consumption data, but the detailed measurement method (meter/instrument versus counter or derived estimate) is not confirmed here, so this audit does not classify its energy labels as verified direct measurements. W could be derived as J/s only if the actual file definitions confirm each value is energy consumed over exactly that interval and its method measures system energy. Its record has a License heading but no license value was displayed when checked. Its schema does not provide current live network rates, GPU utilization, RAM percentage/MB, or disk MB/s; the hardware is mostly server infrastructure and the collector is not Windows. The dataset has **not** been downloaded or used. Obtain and inspect the source documentation, actual files and license before adoption.

### SPECpower_ssj2008

SPEC's [published results](https://spec.org/power_ssj2008/results/) report average active power in watts measured by a power analyzer and accumulated by PTDaemon. The [result field documentation](https://www.spec.org/osg/power/docs/SPECpower_ssj2008-Result_File_Fields.html) describes ten workload load levels including active idle, each measurement interval lasting 240 seconds. The [run rules](https://spec.org/power/docs/specpower_ssj2008-run_reporting_rules/) specify server-class Java benchmark runs and system configuration disclosure. Public use is subject to SPEC Fair Use Guidelines. This is real measured power for the benchmarked servers and workloads, but it does not provide the per-sample Windows telemetry feature definitions used by this application; benchmark target load is not equivalent to `psutil` CPU utilization or disk/network rates. It is not a directly compatible training table and no raw result corpus has been incorporated.

### 160 Hours of Labeled Power Consumption Dataset of Computer

The [Zenodo record](https://zenodo.org/records/8192914) (DOI `10.5281/zenodo.8192914`), by Arthur Grisel-Davy (University of Waterloo), describes 40 four-hour runs on an Intel NUC and power traces preprocessed from 10 kSPS to 20 samples/second using a median filter, with separate activity labels. It is a candidate for meter power, but exact meter setup, rights/license and paired OS telemetry feature definitions were not verified sufficiently here, and a newer version is indicated by the record. It is not used. Inspect the paper, current version, files and rights before deciding whether any conversion or pairing is scientifically valid.

### SWEAT name ambiguity

The SWEAT record above was found during this audit. Older project documentation asserted there was no canonical SWEAT dataset. That statement was stale and is removed; the existence of the 2026 record does not itself establish a compatible, licensable dataset for this project.

## Adoption decision and limitations

No candidate is currently verified end-to-end for both license/measurement provenance and compatibility with this Windows telemetry. Retain the generated CSV only as a prototype dataset. Do not retrain and label it as measured. Live estimates based on artifacts trained from it are estimates from a synthetic prototype, not validated power readings. Hardware validation has not occurred.

For whole-laptop power, build a dataset from timestamp-aligned OS features and an external calibrated power meter on the target computer across representative workloads, and preserve meter, sampling, hardware, workload, license and provenance documentation. A separate HWiNFO CPU Package Power dataset can support a CPU-only target, but cannot stand in for whole-laptop power. Split by separate runs or machines where possible. A measured dataset may need a reduced, explicitly mapped common feature set; never convert unmatched columns by guessing.

