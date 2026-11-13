# Deviations

None executed. Stage 0 remains incomplete. Metadata inventory before the updated attachment involved no corpus scoring or T6 content.

## Engineering interruption before first model request
Original source IDs contain Windows-forbidden pipe characters. Request-record creation failed before HTTP completion requests (0 request records). Own server exited. New generation01 directory maps source IDs to 24-hex SHA256 filenames; original IDs remain in input/output metadata. No question, seed, sampling setting or model changed. No generated answer was retried.

## Text-processing environment repair
Mining initially failed at import because spaCy was absent; no corpus mining or NLI score was produced. Installed spaCy3.7.5 with cached official en_core_web_sm3.7.1; the installer temporarily downgraded shared .venv NumPy, which was restored to2.4.4. Text-processing execution moved to stage-specific runtime using NumPy1.26.4/SciPy1.14.1. No generated answer was rerun. Exact EVAL03 installed spaCy package provenance was not preserved in its freeze, so byte-equivalence of its installed package cannot be established; unchanged historical code and same named model are used, and this limitation is retained.
