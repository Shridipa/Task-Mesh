# 🚀 TaskMesh – A Distributed Task Queue & Workflow Orchestration Platform

## Overview

TaskMesh is a modern distributed task processing platform designed to execute long-running, asynchronous, and scheduled tasks efficiently. It separates task submission from task execution, allowing applications to remain responsive while background workers process jobs independently.

Instead of executing expensive operations directly inside an application request, TaskMesh places them into a queue where dedicated workers process them asynchronously. This architecture improves scalability, reliability, and fault tolerance while providing complete visibility into every task through an interactive monitoring dashboard.

The project demonstrates concepts used in production-grade distributed systems such as Celery, RabbitMQ workers, Temporal, Apache Airflow, AWS SQS, Google Cloud Tasks, and Kubernetes Job Controllers, while remaining lightweight and educational.

---

# ❓ Why Build TaskMesh?

Modern applications frequently perform operations that should not block users.

Examples include:

* Sending emails
* Processing uploaded files
* Generating reports
* Image or video processing
* AI inference
* Running machine learning pipelines
* Payment processing
* Data synchronization
* Scheduled reminders
* Backup operations

If these operations execute synchronously, users must wait until they complete, resulting in poor performance and an unreliable user experience.

TaskMesh solves this problem by decoupling task execution from user requests.

Instead of performing work immediately, applications submit jobs into TaskMesh, which schedules and executes them independently using background workers.

---

# 💡 The Problem

Imagine an e-commerce platform.

A customer places an order.

Without a task queue:

```
User
 │
 ▼
Place Order
 │
 ├── Update Database
 ├── Generate Invoice
 ├── Send Email
 ├── Notify Warehouse
 ├── Update Inventory
 └── Generate Analytics
```

The customer must wait until every operation finishes.

If one service is slow or unavailable, the entire request becomes slow or fails.

---

# ✅ The TaskMesh Solution

With TaskMesh:

```
User
 │
 ▼
Submit Order
 │
 ▼
TaskMesh API
 │
 ▼
Job Queue
 │
 ├─────────────┐
 ▼             ▼
Worker A    Worker B
 │             │
 ▼             ▼
Send Email   Generate Invoice
 │             │
 ▼             ▼
Complete     Complete
```

The API immediately acknowledges the request while workers process tasks independently in the background.

The result is:

* Faster response times
* Higher throughput
* Better scalability
* Easier failure recovery
* Retry support
* Improved reliability

---

# 🏗 System Architecture

TaskMesh consists of several independent components that work together.

### 1. API Server

The FastAPI backend exposes REST endpoints for:

* Creating jobs
* Viewing jobs
* Managing workers
* Monitoring metrics
* Viewing events
* Scheduling tasks

The API validates incoming requests before storing them in the database.

---

### 2. Job Queue

Every submitted task becomes a Job.

Each job contains:

* Job ID
* Task Type
* Payload
* Priority
* Status
* Retry Count
* Execution Time
* Tenant Information

Jobs move through a lifecycle until completion.

---

### 3. Scheduler

The scheduler continuously checks for delayed or scheduled jobs.

If a job's execution time has arrived, it moves the job into the execution queue where workers can process it.

---

### 4. Workers

Workers are independent background processes responsible for executing tasks.

Each worker:

* Polls pending jobs
* Claims a task
* Executes business logic
* Updates status
* Records execution events
* Reports metrics

Multiple workers can run simultaneously to increase throughput.

---

### 5. Database

TaskMesh stores persistent system state including:

* Jobs
* Workers
* Events
* Retry history
* Execution timestamps

This ensures that jobs survive application restarts and can be audited later.

---

### 6. Redis (Optional)

Redis enables:

* Distributed locking
* Event streaming
* Pub/Sub messaging
* Worker coordination

The project also supports running without Redis using SQLite for local development.

---

### 7. Monitoring Dashboard

The React dashboard provides visibility into the entire system.

It allows operators to observe:

* Queue depth
* Running jobs
* Failed jobs
* Worker status
* Retry statistics
* Historical events
* System health

The dashboard acts as the control center for the distributed platform.

---

# 🔄 Job Lifecycle

Every task progresses through several states.

```
Create Job
      │
      ▼
Pending
      │
      ▼
Scheduled
      │
      ▼
Running
      │
      ▼
Completed
```

If execution fails:

```
Running
    │
    ▼
Retry
    │
    ▼
Retry
    │
    ▼
Failed
    │
    ▼
Dead Letter Queue
```

This lifecycle allows TaskMesh to recover automatically from transient failures while preventing permanently failing jobs from blocking the system.

---

# 🌍 Real-World Applications

TaskMesh can power many types of systems, including:

* Email delivery platforms
* Notification services
* AI inference pipelines
* ETL and data processing workflows
* Image and video processing
* Background API integrations
* Document generation
* Financial transaction processing
* Report generation
* Scheduled maintenance jobs
* IoT event processing
* Cloud automation pipelines

---

# 🎯 Benefits

TaskMesh provides several advantages over synchronous processing.

### Faster Applications

Users receive responses immediately while background tasks execute independently.

---

### Scalability

Additional workers can be started to process larger workloads without changing application code.

---

### Fault Tolerance

Failed jobs are retried automatically before eventually moving to a Dead Letter Queue.

---

### Observability

Every job is traceable through metrics, events, and monitoring dashboards.

---

### Reliability

Task execution survives temporary failures and application restarts.

---

### Extensibility

New job types and worker implementations can be added without modifying the existing architecture.

---

# 🧠 Concepts Demonstrated

TaskMesh showcases several important software engineering concepts:

* Distributed Systems
* Asynchronous Programming
* Background Task Processing
* REST API Design
* Worker Pools
* Task Scheduling
* Event-Driven Architecture
* Database Transactions
* Monitoring & Observability
* Retry Strategies
* Fault Recovery
* Docker Deployment
* Kubernetes Orchestration
* Queue Management
* System Scalability

---
🚀 Getting Started
1. Clone Repository
git clone https://github.com/yourusername/taskmesh.git

cd taskmesh
2. Create Virtual Environment

Windows

python -m venv .venv

.venv\Scripts\activate

Linux/Mac

python3 -m venv .venv

source .venv/bin/activate
3. Install Dependencies
pip install -r requirements.txt
4. Run Backend
python -m uvicorn taskmesh.main:app --reload

Backend runs at

http://127.0.0.1:8000
5. Run Frontend
cd frontend

npm install

npm run dev

Frontend runs at

http://localhost:5173
📘 API Documentation

Swagger UI

http://127.0.0.1:8000/docs

ReDoc

http://127.0.0.1:8000/redoc

---

# 🎓 Learning Objectives

This project was built to explore how modern distributed task processing systems operate internally.

Rather than relying on an existing framework like Celery, TaskMesh demonstrates how core components—including task queues, schedulers, workers, monitoring, retries, persistence, and orchestration—can be designed and implemented from the ground up using FastAPI, SQLAlchemy, Redis, and React.

It serves both as a practical engineering project and as a learning platform for distributed computing concepts used in production cloud-native systems.
"# Task-Mesh"  
