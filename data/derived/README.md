# Derived event artifacts

Hashes of files in this plane enter `config_hash`.
`stewardsim study` reads configs plus derived files only.

For AT-12, the operator supplies every plug-in artifact. Missing any one is `BLOCK`.
No results directory is written on `BLOCK`.

Required under `event_<id>/`:

- `restriction_tape.csv`
- `observed_series.json` — must include `citation` and `hash`
- `cohort.json` — must include `citation` and `hash`

The remaining required artifact is the lock at `configs/locks/at12_<id>.yaml`,
committed before the derived observed series.

Do not invent antibiogram values. Do not write death counts or resistance rates
into this README.

A cited transcript of parked PDFs may live in `antibiograms/`. That transcript
is not an AT-12 event and must not be copied into `event_<id>/` until the
operator names a restriction date and writes a lock file first.

Filenames or values containing mock, dummy, fake, or placeholder are rejected.
