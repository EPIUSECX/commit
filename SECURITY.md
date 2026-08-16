# Security policy

Please report vulnerabilities privately to support@thecommit.company. Do not
open a public issue containing exploit details, access tokens, source code, or
customer data.

Commit treats cloned repositories and published documentation as untrusted
input. New endpoints must default to authenticated access, apply Frappe document
permissions, validate filesystem containment, and constrain outbound network
requests. Public endpoints must return an explicit public DTO and must never
perform mutation or execute stored content.
