# Database migrations

`versions/0001_initial.py` is the baseline PostgreSQL schema revision. Its
`upgrade` and `downgrade` functions accept a SQLAlchemy connection for isolated
tests and use Alembic's active connection when invoked by an Alembic runner.

The migration is metadata-driven so model and migration constraints cannot
silently diverge. PostgreSQL receives the partial unique index that permits at
most one non-deleted active tournament per workspace.
