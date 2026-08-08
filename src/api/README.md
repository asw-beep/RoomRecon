# src/api

**Responsibility:** expose the pipeline as a product — projects, uploads, jobs, status,
artifacts.

FastAPI surface (frozen):

```
POST /projects
POST /projects/{id}/upload
POST /projects/{id}/reconstruct
GET  /projects/{id}/status
GET  /projects/{id}/metadata
GET  /projects/{id}/scene
GET  /projects/{id}/export
```

Also owns the background job worker. Reconstruction is not an HTTP request — it is a job
with real states (queued, running, failed, complete), progress, and resumability after
interruption.

Every job carries: `job_id`, stage, status, duration, error, GPU memory, CPU, and output
artifact paths. This is the observability contract from the engineering plan, and it is
what makes M9 achievable.

Storage is SQLite + `storage/projects/<id>/`. No Postgres, no object storage, no
Redis/Celery until a real multi-user requirement exists (ADR-003).

Tier: T1.
Milestone: M5.
