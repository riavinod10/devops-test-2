# Changelog

## [1.0.0] - 2026-10-25

### Added
- Backend: Flask payment & notification API (`/api/payments`, `/api/notifications`, `/api/stats`, `/health`, `/ready`) with input validation and pytest suite.
- Frontend: nginx-served dashboard that reverse-proxies `/api/*` to the backend.
- Docker: multi-stage backend image (test + non-root runtime targets) and frontend image.
- Kubernetes: `payment-engine` namespace, backend + frontend Deployments, NodePort Services (30500, 30080).
- Jenkins: Declarative Pipeline (Build → Test → Package Containers → Smoke Test).
- IaC: Terraform generating Ansible connection files; Ansible playbook validating host configuration.
- Jira sprint backlog (`jira/sprint-backlog.csv`) and verification script (`scripts/verify-stack.ps1`).
