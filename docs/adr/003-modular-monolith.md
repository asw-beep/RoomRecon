# ADR-003 — Modular Monolith, SQLite, and a Local Job Worker

- **Status:** Accepted
- **Date:** 2026-08-08
- **Related:** ADR-005 (compute strategy)

## Context

RoomRecon is a semester project with one developer, one machine, and no multi-user
requirement. It is nevertheless meant to be a *product*, which creates a temptation to
adopt infrastructure that signals production-readiness — microservices, Postgres, object
storage, Redis + Celery, Kubernetes.

That temptation should be resisted. Infrastructure added to look production-grade consumes
the time that would otherwise go into the thing that actually makes this project strong:
a working pipeline with measured behaviour and documented failure modes.

The real requirements are narrower than they first appear:

- Reconstruction takes minutes to hours, so it cannot be an HTTP request. **A job system is
  genuinely required.**
- Artifacts are large binaries. **The filesystem is the right store for them.**
- Project metadata is small and relational. **SQLite is sufficient.**
- One user, one machine. **There is no horizontal scaling problem to solve.**

## Decision

**A modular monolith.** One codebase, one deployable, with strict internal module
boundaries under `src/`. Modules communicate through defined artifacts and interfaces, not
network calls.

Three supporting choices:

1. **SQLite + local filesystem.** Project metadata in SQLite; artifacts under
   `storage/projects/<id>/{input,frames,poses,sparse,gaussian,mesh,metrics}/`. No
   Postgres, no S3.

2. **A simple local background worker.** Real job states (queued, running, failed,
   complete), progress reporting, and resume after interruption — but an in-process worker,
   not Redis + Celery.

3. **Boundaries enforced by discipline, not by process isolation.** `src/` never imports
   `experiments/`. `gaussian/` never imports `mesh/`. Artifacts crossing boundaries conform
   to `docs/data-contracts.md`.

The module structure is deliberately the shape a service split *would* take. If a real
multi-user requirement ever arrives, the seams already exist.

## Consequences

**Positive**

- Development, debugging, and deployment stay simple. One process to run, one to inspect.
- No distributed-systems failure modes to reason about — no partial failures across
  services, no network partitions, no eventual consistency.
- Effort goes into the pipeline, evaluation, and viewer, which is where this project's
  value actually is.
- Clean-machine reproducibility (Gate G9) is realistically achievable. It would not be with
  a multi-service stack.

**Negative**

- No horizontal scaling. Concurrent reconstructions are limited by one GPU on one machine.
  Accepted: multi-user is explicitly out of scope for v1.
- Module boundaries rely on discipline. Nothing at runtime prevents a bad import, so this
  needs attention in review.
- SQLite handles concurrent writers poorly. Acceptable at one user; would need revisiting
  at ten.
- A single process means a crash takes everything down. Mitigated by job resumability,
  which is required anyway for pre-emptible cloud sessions (ADR-005).

**Neutral**

- Job orchestration must be written rather than adopted from Celery. Small, but real work.

## Alternatives considered

**Microservices.** Rejected. Every stated benefit — independent scaling, independent
deployment, team autonomy — addresses a problem this project does not have. Would multiply
the operational surface for zero user-visible gain.

**Postgres + S3/MinIO from the start.** Rejected. Adds two services and a network hop to
solve concurrency and durability problems that one user on one laptop does not have.
Revisit only when multi-user deployment is a real requirement.

**Redis + Celery for jobs.** Rejected for v1, and the least firm of these rejections. It is
the natural upgrade the moment reconstruction needs to run on a separate machine from the
API. The job interface should be written so this swap is possible without touching the
pipeline.

**No job system, synchronous HTTP.** Rejected outright. Hour-long HTTP requests are not a
design. Progress reporting is a product requirement, not a convenience.
