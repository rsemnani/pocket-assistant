"""Background workers: reminder/escalation scans, interpret/execute jobs, CC jobs.

Phase 1 ships the reminder/escalation scan as a directly-callable function (no queue
required); a Redis-backed queue is wired in a later phase behind the same call sites.
"""
