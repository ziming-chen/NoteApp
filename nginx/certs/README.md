# Local lab TLS files

Generate `notesapp.crt` and `notesapp.key` here before starting the HTTPS overlay.
Follow [the Session 05 instructions](../../docs/session05/README.md#run-the-submitted-application).
Both runtime files are ignored. Each clone generates its own certificate and key.
The public certificate observed during the audit is archived separately in
`docs/session05/lab1/configuration/notesapp.crt`; that evidence certificate does
not include its private key and is not a ready-to-run TLS identity for a new clone.
