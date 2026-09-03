# Security policy

## Scope

Unskip is a local static scanner. It reads Git metadata, diff text, and files
selected by its scan mode. It never runs target code and never uploads data.
The scanner is not a sandbox for arbitrary programs and is not a replacement
for a project's security tooling or test suite.

## Reporting a vulnerability

Please do not put secrets, proprietary source, or an undisclosed exploit in a
public issue.

For a sensitive report, open the repository's GitHub **Security** tab and use
**Report a vulnerability** when that private channel is available. Include:

- the Unskip version and Python/OS details;
- the command and input mode used;
- a minimal reproduction with confidential data removed;
- the expected and observed behavior; and
- any safety impact, such as target-code execution, unintended file access, or
  data disclosure.

If private reporting is unavailable, file a public issue containing only a
sanitized description and say that the report is security-sensitive. Do not
attach confidential diffs or credentials.

## Security boundaries

- A finding is a static review signal, not proof of cheating or correctness.
- Same-hunk and path-targeted acknowledgements are review metadata, not
  authorization or access-control mechanisms.
- Git and filesystem permissions still govern what the process can read.
- The package declares zero runtime dependencies; packaging tools used to build
  it are separate from the runtime contract.

## Safe handling

Run Unskip with the repository permissions appropriate for the review. Treat
diffs, file names, finding text, and acknowledgement reasons as untrusted
content when forwarding output to another system.
