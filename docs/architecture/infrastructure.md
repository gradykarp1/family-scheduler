# Infrastructure & Deployment

## Overview

The Family Scheduler follows a phased deployment strategy: start simple with local development to learn agent patterns, then evolve to cloud deployment to learn scaling and infrastructure.

## Phase 1: Local Development

**Goal:** Learn LangGraph and agent patterns without infrastructure complexity

### Architecture

```
┌─────────────────────────┐
│      User (CLI/Web)     │
└───────────┬─────────────┘
            │ HTTP
            ▼
┌─────────────────────────┐
│   FastAPI Application   │
│                         │
│  • HTTP endpoints       │
│  • LangGraph agents     │
│    (in-process)         │
│  • Business logic       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   SQLite Database       │
│   (local file)          │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│   LLM API               │
│   (OpenAI/Anthropic)    │
└─────────────────────────┘
```

### Technology Stack

**Runtime:**
- Python 3.11+
- Virtual environment (venv or Poetry)

**Web Framework:**
- FastAPI (async support, automatic OpenAPI docs)
- Uvicorn (ASGI server)

**Agent Framework:**
- LangGraph for orchestration
- LangChain for LLM utilities

**Database:**
- SQLite (file-based, zero config)
- SQLAlchemy ORM
- Alembic for migrations

**LLM:**
- OpenAI API (GPT-4) or Anthropic API (Claude)
- Environment variable for API key

### Setup Instructions

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
alembic upgrade head

# Configure environment
cp .env.example .env
# Edit .env with your LLM API key

# Run development server
uvicorn src.api.main:app --reload
```

### Development Workflow

1. **Code Changes:** Edit Python files
2. **Auto-Reload:** FastAPI dev server reloads automatically
3. **Test API:** Use http://localhost:8000/docs (Swagger UI)
4. **Inspect DB:** Use SQLite browser or SQL queries
5. **View Logs:** Console output from Uvicorn

### Cost

**$0 infrastructure** (only LLM API usage)
- OpenAI GPT-4: ~$0.01-0.03 per API call
- Anthropic Claude: ~$0.01-0.02 per API call
- Estimated: $5-20/month for development

### Pros
- Instant startup, no deployment overhead
- Easy debugging (all logs in console)
- Fast iteration cycle
- Learn agent patterns without cloud complexity

### Cons
- Only accessible from development machine
- No horizontal scaling
- Single-threaded agent execution
- SQLite doesn't support high concurrency

---

## Phase 2: Cloud Deployment (GCP)

**Goal:** Learn container orchestration, task queues, and horizontal agent scaling

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          User Interface                          │
│                   (Web Browser / Mobile App)                     │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ HTTPS
                                 ▼
                    ┌────────────────────────┐
                    │   Cloud Load Balancer  │
                    └────────────┬───────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
    ┌────────────────────────┐      ┌──────────────────────┐
    │   API Service          │      │   Static Assets      │
    │   (Cloud Run)          │      │   (Cloud Storage +   │
    │                        │      │    CDN)              │
    │  • Receives requests   │      └──────────────────────┘
    │  • Creates tasks       │
    │  • Returns quickly     │
    └──────────┬─────────────┘
               │
               │ Push task
               ▼
    ┌──────────────────────────────────────────┐
    │         Redis (Memorystore)              │
    │         Task Queue                       │
    │                                          │
    │  • Celery task queue                     │
    │  • Durable task storage                  │
    │  • Pub/sub for notifications             │
    └──────────┬───────────────────────────────┘
               │
               │ Pull tasks
               ▼
    ┌──────────────────────────────────────────┐
    │      Agent Worker Pool (Cloud Run)       │
    │                                          │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐│
    │  │ Worker 1 │ │ Worker 2 │ │ Worker N ││
    │  │          │ │          │ │          ││
    │  │ LangGraph│ │ LangGraph│ │ LangGraph││
    │  │ Executor │ │ Executor │ │ Executor ││
    │  └──────────┘ └──────────┘ └──────────┘│
    │                                          │
    │  Auto-scales: 1-10 instances             │
    └──────┬───────────────────────────┬───────┘
           │                           │
           │ Read/Write                │ Checkpoint
           ▼                           ▼
    ┌─────────────────┐        ┌─────────────────┐
    │  Cloud SQL      │        │  Cloud Storage  │
    │  (PostgreSQL)   │        │                 │
    │                 │        │  • LangGraph    │
    │  • Events       │        │    checkpoints  │
    │  • Resources    │        │  • Allows any   │
    │  • Conflicts    │        │    worker to    │
    │  • Constraints  │        │    resume       │
    └─────────────────┘        └─────────────────┘
```

### Technology Stack

**Google Cloud Platform Services:**

1. **Cloud Run** (API + Workers)
   - Serverless containers
   - Auto-scales from 0 to N instances
   - Pay only for request handling time
   - Built-in HTTPS and load balancing

2. **Cloud SQL** (PostgreSQL)
   - Managed PostgreSQL database
   - Automated backups
   - High availability
   - Point-in-time recovery

3. **Memorystore** (Redis)
   - Managed Redis instance
   - Used for Celery task queue
   - Pub/sub for real-time notifications
   - Low latency (<1ms)

4. **Cloud Storage** (GCS)
   - Object storage for LangGraph checkpoints
   - Enables distributed agent execution
   - Any worker can resume workflow

5. **Cloud Build** (CI/CD)
   - Automated Docker image builds
   - Deploy on git push
   - Integration with GitHub

6. **Cloud Logging & Monitoring**
   - Centralized logs from all services
   - Metrics and dashboards
   - Alerting

**Application Stack:**
- **FastAPI** for API layer
- **Celery** for task queue management
- **LangGraph** for agent orchestration
- **SQLAlchemy** for database ORM
- **Docker** for containerization

### Agent Scaling Workflow

**Request Flow:**

1. **User Request:**
   ```
   POST /events
   {
     "message": "Schedule soccer practice Saturday at 2pm"
   }
   ```

2. **API Service (Cloud Run):**
   ```python
   @app.post("/events")
   async def create_event(request: EventRequest):
       # Validate request
       # Create Celery task
       task = process_event.apply_async(args=[request.dict()])

       # Return immediately
       return {
           "status": "processing",
           "task_id": task.id,
           "status_url": f"/tasks/{task.id}"
       }
   ```

3. **Redis Queue:**
   - Task stored in Redis: `{"task_id": "abc123", "args": {...}, "status": "pending"}`

4. **Agent Worker:**
   ```python
   @celery_app.task
   def process_event(event_data):
       # Run LangGraph workflow
       state = {
           "user_request": event_data["message"],
           ...
       }

       result = orchestrator_graph.invoke(state)

       # Save checkpoint to Cloud Storage
       save_checkpoint(state, "gs://bucket/checkpoints/abc123")

       # Update database
       db.commit()

       return {"status": "complete", "event_id": "..."}
   ```

5. **User Polling or Webhook:**
   ```
   GET /tasks/abc123
   {
     "status": "complete",
     "result": {"event_id": "...", "message": "Event confirmed!"}
   }
   ```

### Auto-Scaling Configuration

**Cloud Run Worker Scaling:**
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: agent-workers
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/target: "5"  # Target 5 concurrent requests per instance
    spec:
      containers:
      - image: gcr.io/project/agent-worker:latest
        env:
        - name: CELERY_BROKER_URL
          value: "redis://memorystore-ip:6379/0"
        resources:
          limits:
            cpu: "2"
            memory: "2Gi"
```

**Scaling Triggers:**
- **Queue Depth:** More tasks in Redis → scale up workers
- **CPU Usage:** High CPU → scale up
- **Request Latency:** Slow response → scale up
- **Idle Time:** No tasks → scale down to minimum

**Example Scaling Behavior:**
- Normal: 1-2 workers (minimal cost)
- Busy (5 concurrent events): 3-5 workers
- Peak (10+ concurrent events): 8-10 workers
- Off-hours: Scale to 1 worker (save cost)

### Deployment Process

**1. Containerize Application:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# API service
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Worker (override CMD)
# CMD ["celery", "-A", "src.workers.celery_app", "worker", "--loglevel=info"]
```

**2. Build and Push:**

```bash
# Build image
docker build -t gcr.io/PROJECT_ID/family-scheduler:latest .

# Push to Google Container Registry
docker push gcr.io/PROJECT_ID/family-scheduler:latest
```

**3. Deploy Services:**

```bash
# Deploy API service
gcloud run deploy api-service \
  --image gcr.io/PROJECT_ID/family-scheduler:latest \
  --platform managed \
  --region us-central1 \
  --set-env-vars="DATABASE_URL=..." \
  --allow-unauthenticated

# Deploy worker service
gcloud run deploy agent-workers \
  --image gcr.io/PROJECT_ID/family-scheduler:latest \
  --platform managed \
  --region us-central1 \
  --set-env-vars="DATABASE_URL=...,CELERY_BROKER_URL=..." \
  --command="celery" \
  --args="-A,src.workers.celery_app,worker,--loglevel=info" \
  --cpu=2 \
  --memory=2Gi \
  --min-instances=1 \
  --max-instances=10
```

**4. Set Up Infrastructure:**

```bash
# Create PostgreSQL instance
gcloud sql instances create family-scheduler-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=us-central1

# Create Redis instance
gcloud redis instances create family-scheduler-redis \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_6_x

# Create Cloud Storage bucket
gsutil mb -c STANDARD -l us-central1 gs://family-scheduler-checkpoints
```

### Cost Estimation (Monthly)

**Infrastructure:**
- **Cloud Run (API):** $5-10
  - Mostly idle, pay per request
  - ~1M requests/month: ~$5

- **Cloud Run (Workers):** $15-30
  - 1 worker minimum (always on): ~$10/month
  - Auto-scaling to 5 workers during peak: ~$5-20/month

- **Cloud SQL (PostgreSQL):** $10-15
  - db-f1-micro instance (shared CPU, 0.6GB RAM)
  - 10GB storage

- **Memorystore (Redis):** $5-10
  - Basic tier, 1GB capacity

- **Cloud Storage:** $1-2
  - Storage + operations for checkpoints

- **Networking:** $5-10
  - Egress, load balancing

**Total Infrastructure: $41-77/month**

**LLM API Usage:** $10-30/month
- Depends on family usage
- Estimated 50-150 agent workflows/month

**Total Estimated Cost: $51-107/month**

**Cost Optimization Tips:**
- Use db-f1-micro for database (smallest instance)
- Set min-instances=1 for workers (not 0, to avoid cold starts)
- Use Cloud Run's pay-per-use model
- Monitor and adjust scaling thresholds
- Use cheaper LLM models for non-critical agents

### Monitoring & Observability

**Key Metrics to Track:**

1. **Agent Performance:**
   - Task processing time
   - Success/failure rate
   - Agent-level latency (per agent type)
   - LLM token usage

2. **Infrastructure:**
   - Cloud Run instance count
   - CPU/memory utilization
   - Database query performance
   - Redis queue depth

3. **Business Metrics:**
   - Events created per day
   - Conflicts detected/resolved
   - User satisfaction (explicit feedback)

**Logging Strategy:**
```python
import logging
from google.cloud import logging as cloud_logging

# Initialize Cloud Logging
client = cloud_logging.Client()
client.setup_logging()

# Structured logging
logger = logging.getLogger(__name__)
logger.info("Agent workflow started", extra={
    "task_id": "abc123",
    "agent": "orchestrator",
    "user_id": "user_456"
})
```

**Dashboards:**
- Request rate and latency
- Worker scaling over time
- Database connection pool
- Error rates by agent type
- Cost tracking

**Alerts:**
- Error rate > 5%
- Worker queue depth > 50
- Database CPU > 80%
- API latency > 2s
- Daily cost > $5

### Disaster Recovery

**Backups:**
- **Database:** Automated daily backups (Cloud SQL)
- **Point-in-time recovery:** Up to 7 days
- **Checkpoints:** Retained in Cloud Storage for 30 days

**Recovery Procedures:**
1. Database failure: Restore from latest backup
2. Worker crash: Task automatically retried by Celery
3. Data corruption: Point-in-time recovery
4. Region outage: Manual failover to backup region (future)

---

## Phase 3: Advanced Scaling (Future)

**Potential Enhancements:**

1. **Multi-Region Deployment:**
   - Deploy to multiple GCP regions
   - Global load balancing
   - Lower latency for distributed families

2. **Kubernetes (GKE):**
   - More control over scaling
   - Complex orchestration
   - Service mesh for observability

3. **Serverless Functions:**
   - Cloud Functions for simple tasks
   - Even more granular scaling
   - Lower cost for sporadic usage

4. **Edge Caching:**
   - CDN for static content
   - Redis for query results
   - Reduce database load

5. **Advanced Monitoring:**
   - Distributed tracing (Cloud Trace)
   - APM tools
   - Real-time anomaly detection

---

## Development to Production Checklist

**Before Deploying Phase 2:**

- [ ] Comprehensive test suite (unit + integration)
- [ ] Load testing (simulate concurrent agent workflows)
- [ ] Security review (API authentication, input validation)
- [ ] Database migration plan (SQLite → PostgreSQL)
- [ ] Environment variable management (secrets)
- [ ] Error handling and retry logic
- [ ] Monitoring and alerting setup
- [ ] Documentation for deployment process
- [ ] Cost budget and alerts configured
- [ ] Backup and recovery procedures tested

---

*Last Updated: 2026-01-08*
