# Parameter locks

Required lock name: `at12_<id>.yaml`

The lock is committed before any derived observed series is copied into
`data/derived/event_<id>/`.

Missing this lock ⇒ AT-12 `BLOCK`. The gate does not write a results directory.

Do not invent parameters from memory. Do not record death counts or resistance rates here.
