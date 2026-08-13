# Raw ingest

Operator-supplied source files for a retrodiction event live here.

This plane may use the network. `src/stewardsim` never does.

Place sources under a directory named for the event id, each with a citation.
Do not invent an observed series, an antibiogram, or a cohort.
Do not write death counts or resistance rates into this file.

Agents do not choose the event. The event is a plug-in supplied by the operator.
The gate never modifies this plane.

`parked_antibiograms/` holds operator-supplied PDF source tables. They are not
an AT-12 event. Do not copy them into `data/derived/event_*/` until the
operator names a restriction date and supplies a lock file first.
