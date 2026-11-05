# ADR 0002: Provider data is untrusted input

Status: accepted (2026-11-05)

Job titles, locations and URLs come from third parties and end up in Markdown that may be posted to chat tools. They are treated like user input: control and format characters are removed, length is capped, Markdown metacharacters are escaped, and only plain `https` URLs are rendered (parentheses and angle brackets are percent-encoded so a link cannot terminate early). Parsers use defensive accessors instead of trusting shapes. Config tokens are restricted to a safe character set so they can only select a board, never alter the request path or host. The transport refuses non-HTTPS URLs, applies a timeout and caps the response size.

Trade-off: legitimate titles with Markdown characters show with backslashes in raw Markdown. Rendering is conservative on purpose.
