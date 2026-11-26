# Helpdesk and Incident Foundation

Migration 005 creates ticket, category, comment and activity persistence. Ticket identifiers are unique and external source/event pairs are unique to support idempotent webhook ingestion. A resolved Grafana alert must not automatically resolve or close its ticket.

This schema is a persistence foundation only. Ticket service methods must enforce object-level authorization, valid state transitions, requester/assignee/team consistency, audit logging, SLA calculation and transactional activity records. Internal comments must never be exposed to requester-facing views.
