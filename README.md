# Mar Carter Portfolio | cx-ops-security-labs
## CX operations, security research, and risk-aware workflow design

I am a CX and operations professional building cybersecurity research skills, with a focus on AI-enabled workflows, risk analysis, Linux systems, and operational trust.

My background began in high-growth platform operations, customer support leadership, fraud prevention, and trust and safety work in the logistics technology sector. I worked on operational responses to abuse patterns such as VOIP spoofing, payment fraud, chargebacks, and coordinated account attacks. That experience shaped how I think about risk: many failures occur at the boundaries between people, systems, incentives, workflows, and unclear ownership.

I am currently expanding that foundation through formal training in cybersecurity, risk assessment, and security governance. My work emphasizes practical controls, incident analysis, documentation, and operational resilience.

I am especially interested in roles where CX, operations, security, and product reality intersect. These are environments where technical systems, customer-facing workflows, escalation paths, and human judgment must be aligned to produce stable and trustworthy outcomes.

Beyond security practice, I care about open technology, digital autonomy, privacy-aware infrastructure, and resilient systems design. My projects explore Linux environments, security labs, incident documentation, and the operational mechanics of real systems.

This repository serves as a portfolio of labs, risk analyses, incident journals, and technical exercises that document my ongoing development in cybersecurity and systems operations.

## API and systems labs

### [Payment Retry Investigation Lab](payment-retry-lab/README.md)

Python and SQLite investigation of Square Sandbox REST APIs: idempotent retries, conflicting parameters, recovery after discarding a response, concurrent requests, and cursor pagination. Includes a local evidence journal, five offline tests, and a [reproduction runbook](payment-retry-lab/RUNBOOK.md).

# Incident response journals

| Entry | Scenario | File |
|-------|----------|------|
| Template | Reusable incident handler journal template | [incident-log.md](incident-log.md) |
| Short template | Compact journal prompt template | [incident-journal-short-template.md](incident-journal-short-template.md) |
| 001 | Fictional primary care clinic ransomware incident | [incident-log-01.md](incident-log-01.md) |
| 002 | Malicious password-protected spreadsheet and file hash investigation | [incident-log-filehashing.md](incident-log-filehashing.md) |
| 003 | Data theft through forced browsing | [incident-log-datatheft.md](incident-log-datatheft.md) |
| 004 | Wazuh Filebeat ingestion failure on Linux VirtualBox host | [incident-log-wazuh-filebeat.md](incident-log-wazuh-filebeat.md) |
| 005 | Capturing and analyzing network traffic with tcpdump | [incident-log-tcpdump.md](incident-log-tcpdump.md) |

Supporting walkthroughs and screenshots are stored in [assets/](assets/).

