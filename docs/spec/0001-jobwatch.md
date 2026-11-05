# Spec 0001: jobwatch

## Stories

### US1: Strict configuration
- Given a TOML file with `[[source]]` tables (`name`, `kind`, `token`), when loaded, then it is validated: known kind, token matching `[A-Za-z0-9_-]{1,64}`, unique names, at most 50 sources, no unknown keys.
- Given an invalid or missing file, then the CLI exits `2` with a one-line message that never echoes file contents.

### US2: Provider adapters
- Given a Greenhouse, Ashby or Lever response, then only remote roles are kept, with a provider-qualified id.
- Given wrong types, missing fields or non-JSON, then parsing never raises on shape; non-JSON becomes a content-free `FetchError`.

### US3: Baselining
- Given a source that has never answered successfully, when it answers, then its roles are recorded and nothing is reported as new for it.
- Given a baselined source, then only ids not seen before are reported.

### US4: Partial failure
- Given one source failing, then the others are reported and the failure is listed under "Partial coverage".
- Given every source failing, then state is not written and the exit code is `3`.

### US5: Durable state
- Given a crash or failed write, then the previous state file is intact and no temp files remain.
- Given an unreadable or invalid state file, then it is moved to `<name>.corrupt` and a baseline is re-recorded, with a warning.
- Given more than 5000 ids, then the most recently seen are kept.

### US6: Safe output
- Given hostile titles or links, then Markdown is escaped, control characters stripped, length capped, and non-`https` links replaced by "no valid link".

### US7: Offline demo
- Given no network, when `python -m jobwatch.demo` runs, then it shows baselining, a provider outage, new roles, hostile input and a corrupt state file, deterministically.

## Non-goals
Scraping search engines or career pages, ranking, applying, notification delivery, scheduling.
