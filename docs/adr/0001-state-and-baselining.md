# ADR 0001: Per-source baselining and atomic, versioned state

Status: accepted (2026-11-05)

A monitor is only useful if "new" is trustworthy. Two failure modes ruin that: flooding the user with every existing role after an outage, and losing state to a bad write. State therefore records, per source, whether it has ever answered (`baselined`), and maps each role id to the date it was last seen. A source is allowed to report new roles only after it has been recorded once. State is versioned JSON written to a temp file, fsynced and renamed into place; an invalid file is moved aside, never overwritten, so evidence is kept.

Alternatives considered: one global "first run" flag (a source down on day one would later flood the report), a database (more machinery than a few thousand ids justify).

Trade-off: a corrupt state file costs one silent re-baseline (roles published in that window are not reported). The warning makes that visible instead of hiding it.
