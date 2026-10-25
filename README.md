# Enterprise Payment & Notification Engine — DevOps Capstone

A multi-tier fintech app (nginx **frontend** + Flask **backend**) taken through
Git release flow → Jira sprint → Jenkins pipeline → Docker → Kubernetes →
Terraform + Ansible.

```
devops-test-c/
├── backend/                 Flask API (payments + notifications), pytest suite, multi-stage Dockerfile
│   ├── app/main.py
│   ├── tests/test_api.py
│   ├── Dockerfile           targets: test (Jenkins) / runtime (default, non-root)
│   ├── requirements.txt  requirements-dev.txt  pytest.ini  .dockerignore
├── frontend/                nginx dashboard; /api/* proxied to backend
│   ├── Dockerfile
│   ├── nginx/default.conf.template
│   └── public/ index.html  app.js  styles.css
├── k8s/                     00-namespace, 10-backend (ConfigMap+Deployment+NodePort 30500), 20-frontend (Deployment+NodePort 30080)
├── Jenkinsfile              Declarative pipeline: Preflight → Build → Test → Package Containers → Smoke Test
├── jenkins/Dockerfile       OPTIONAL Jenkins image with Docker CLI
├── terraform/               local provider → writes ansible/generated/{inventory.ini,connection.json,app.env}
├── ansible/playbooks/validate-hosts.yml
├── jira/sprint-backlog.csv  7 sprint tickets with story points
├── scripts/verify-stack.ps1 Docker + K8s + end-to-end checks
├── VERSION  CHANGELOG.md  .gitignore  .gitattributes
```

## Architecture & ports

| Component | Docker (task 4) | Kubernetes (task 5) |
|---|---|---|
| Backend `payment-backend:1.0.0` | `localhost:5000` | Service `payment-backend:5000`, NodePort **30500** |
| Frontend `payment-frontend:1.0.0` | `localhost:8081` (8080 = Jenkins) | Service `payment-frontend:80`, NodePort **30080** |

The frontend reaches the backend by the name `payment-backend` — the container
name on Docker network `payments-net` and the Service name in namespace
`payment-engine`. Backend state is in memory (no DB in scope), so it runs as
1 replica / 1 gunicorn worker; frontend runs 2 replicas.

API: `GET /health`, `GET /ready`, `GET|POST /api/payments`, `GET /api/payments/<id>`,
`GET /api/notifications`, `GET /api/stats`.
POST body: `{"payer":"Alice","payee":"Bob","amount":1500.50,"currency":"INR","method":"UPI"}`
(currency: INR/USD/EUR/GBP; method: UPI/CARD/NETBANKING/WALLET; amount 0.01–1,000,000, max 2 decimals).

## Prerequisites

Docker Desktop running with **Kubernetes enabled**; Git; Terraform ≥ 1.5 (Windows);
Ansible in Ubuntu WSL; Jenkins at `http://localhost:8080`; a GitHub repo (empty) for this project; a Jira Software project with a Scrum board.

Run order: **0 → 1 (Git) → 4 (Docker) → 5 (K8s) → 3 (Jenkins) → 6 (IaC) → 2 (Jira)**.
Jenkins needs the repo pushed first; Jira is closed last once everything is done.

---

## 0. Preflight — Windows PowerShell

```powershell
cd D:\CCodes\devops-test-c
git --version
docker version --format "Docker client {{.Client.Version}} / server {{.Server.Version}}"
kubectl config use-context docker-desktop
kubectl get nodes
terraform version
git config user.name
git config user.email
```

Success: Docker shows a server version, `kubectl get nodes` shows `docker-desktop  Ready`.
If `git config user.name/email` prints nothing, run
`git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`.

## 1. Git — release-v1.0 → main → push (PowerShell)

Create an **empty** GitHub repo first (no README/.gitignore), then set `$RepoUrl`.
`git push` may open a GitHub sign-in window (Git Credential Manager) — sign in there.

```powershell
cd D:\CCodes\devops-test-c
$RepoUrl = "https://github.com/<your-github-username>/devops-test-c.git"   # <-- set this

git init -b main
git add .gitignore .gitattributes README.md
git commit -m "chore: project scaffold"

git switch -c release-v1.0
git add backend
git commit -m "feat(backend): payment and notification API with validation and tests"
git add frontend
git commit -m "feat(frontend): dashboard with nginx reverse proxy to backend"
git add k8s
git commit -m "feat(k8s): namespace, deployments and NodePort services"
git add Jenkinsfile jenkins
git commit -m "ci(jenkins): declarative build-test-package pipeline"
git add terraform ansible scripts jira
git commit -m "feat(iac): terraform connection files, ansible validation, verify script, jira backlog"
git add VERSION CHANGELOG.md
git commit -m "release: v1.0.0"

git switch main
git merge --no-ff release-v1.0 -m "Merge branch 'release-v1.0' into main"
git tag -a v1.0.0 -m "Release v1.0.0"
git status
git log --oneline --graph --all --decorate

git remote add origin $RepoUrl
git push -u origin main
git push -u origin release-v1.0
git push origin v1.0.0
git branch -a
```

Success: graph shows the 6 release commits joined into `main` by a merge commit;
`git branch -a` lists `remotes/origin/main` and `remotes/origin/release-v1.0`.

## 4. Docker — build, tag, run, verify (PowerShell)

```powershell
cd D:\CCodes\devops-test-c

docker build --target runtime --build-arg APP_VERSION=1.0.0 -t payment-backend:1.0.0 -t payment-backend:latest .\backend
docker build -t payment-frontend:1.0.0 -t payment-frontend:latest .\frontend
docker images --filter "reference=payment-*"

docker rm -f payment-backend payment-frontend 2>$null
docker network inspect payments-net *> $null
if ($LASTEXITCODE -ne 0) { docker network create payments-net }

docker run -d --name payment-backend  --network payments-net -p 5000:5000 --restart unless-stopped payment-backend:1.0.0
docker run -d --name payment-frontend --network payments-net -p 8081:80   --restart unless-stopped payment-frontend:1.0.0
Start-Sleep -Seconds 8

docker ps --filter "name=payment-" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
Invoke-RestMethod http://localhost:5000/health
Invoke-RestMethod http://localhost:8081/backend-health
```

Success: both containers `Up … (healthy)`; health calls return `status ok`.
Open http://localhost:8081 to use the dashboard.

## 5. Kubernetes — deploy + NodePort (PowerShell)

Uses the images built in step 4 (Docker Desktop's Kubernetes shares the local image store).

```powershell
cd D:\CCodes\devops-test-c
kubectl config use-context docker-desktop
kubectl apply -f .\k8s\
kubectl rollout status deployment/payment-backend  -n payment-engine --timeout=120s
kubectl rollout status deployment/payment-frontend -n payment-engine --timeout=120s
kubectl get deploy,pods,svc -n payment-engine -o wide

Invoke-RestMethod http://localhost:30500/health
Invoke-RestMethod http://localhost:30080/backend-health

powershell -ExecutionPolicy Bypass -File .\scripts\verify-stack.ps1
```

Success: 1/1 backend and 2/2 frontend pods `Running`/`Ready`; services `NodePort`
`5000:30500/TCP` and `80:30080/TCP`; script ends with `ALL CHECKS PASSED`.
Dashboard: http://localhost:30080

If pods show `ErrImagePull`/`ImagePullBackOff`: your Docker Desktop cluster
doesn't share the local image store (the "kind" cluster type). Switch Kubernetes
to the kubeadm cluster in Docker Desktop settings, or send me the
`kubectl describe pod` output.

## 3. Jenkins — Declarative Pipeline

### 3a. Check Jenkins can run Docker (PowerShell)

```powershell
$J = docker ps --filter "publish=8080" --format "{{.Names}}"
"Jenkins container: $J"
docker exec $J docker version --format "{{.Server.Version}}"
```

- Prints a version → go to **3c**.
- Error (`docker: not found` / `permission denied` / cannot connect) → do **3b**.

### 3b. (Only if 3a failed) Jenkins with Docker access (PowerShell)

Stops (does not delete) your current Jenkins and starts a new one with the Docker
CLI and the host Docker socket. It uses a fresh home volume, so you'll do the
Jenkins setup wizard again (Install suggested plugins + create admin user).
Running as root is for this local lab only.

```powershell
cd D:\CCodes\devops-test-c
$J = docker ps --filter "publish=8080" --format "{{.Names}}"
docker build -t jenkins-docker:lts .\jenkins
if ($J) { docker stop $J }
docker run -d --name jenkins-docker -u root -p 8080:8080 -p 50000:50000 `
  -v jenkins_docker_home:/var/jenkins_home `
  -v /var/run/docker.sock:/var/run/docker.sock `
  --restart unless-stopped jenkins-docker:lts
Start-Sleep -Seconds 40
docker exec jenkins-docker docker version --format "{{.Server.Version}}"
docker exec jenkins-docker cat /var/jenkins_home/secrets/initialAdminPassword
```

Paste the printed password at http://localhost:8080 to unlock.

### 3c. Create and run the job (Jenkins UI)

1. http://localhost:8080 → **New Item** → name `payment-engine-pipeline` → **Pipeline** → OK.
2. **Pipeline** section → Definition **Pipeline script from SCM** → SCM **Git**.
3. Repository URL = your GitHub repo URL. If the repo is private, add credentials (Username = GitHub user, Password = a GitHub personal access token) — enter these yourself.
4. Branch Specifier `*/main`, Script Path `Jenkinsfile` → **Save**.
5. **Build Now**. Open the build → stages Preflight, Build, Test, Package Containers (Backend/Frontend in parallel), Smoke Test should all be green; **Test Result** shows 22 passing tests.

Images packaged by Jenkins land in the same Docker Desktop engine
(`payment-backend:build-<N>`, `payment-frontend:build-<N>`, plus `1.0.0`/`latest`).

## 6. IaC — Terraform (PowerShell) then Ansible (Ubuntu/WSL)

**Windows PowerShell**

```powershell
cd D:\CCodes\devops-test-c\terraform
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=main.tfplan
terraform apply main.tfplan
terraform output
Get-ChildItem ..\ansible\generated
Get-Content ..\ansible\generated\inventory.ini
```

Success: `Apply complete! Resources: 3 added`; `ansible\generated\` has
`inventory.ini`, `connection.json`, `app.env`.

**Ubuntu (WSL)**

```bash
cd /mnt/d/CCodes/devops-test-c/ansible
ansible --version
ansible-inventory -i generated/inventory.ini --graph
ansible-playbook -i generated/inventory.ini playbooks/validate-hosts.yml --syntax-check
ansible-playbook -i generated/inventory.ini playbooks/validate-hosts.yml
cat generated/validation-report.txt
```

Success: `PLAY RECAP` shows `failed=0` for `frontend-node` and `backend-node`.
The endpoint probe is a soft check: `HTTP 200` if WSL can reach Windows
`localhost`, otherwise `unreachable from this host` (WSL NAT networking) — the play still passes.

## 2. Jira — sprint close-out (Jira UI)

1. Project → **Backlog**. Create the 7 issues from `jira/sprint-backlog.csv`
   (or import it: ⚙ Settings → System → External System Import → CSV — needs Jira admin; map *Story Points*).
2. Drag all 7 into the active sprint (or **Create sprint** → add them → **Start sprint**).
3. **Active sprints** board → move every ticket to **Done**.
4. **Complete sprint** → confirm all issues completed.
5. **Reports → Burndown Chart** (and **Sprint Report**) → select the sprint → review/screenshot: remaining story points drop to 0 (all 21 points completed).

---

## What was verified before delivery

| Check | Result |
|---|---|
| Backend pytest suite (22 tests) | ✅ passed |
| Backend under gunicorn: /health, POST /api/payments, /api/stats | ✅ passed |
| K8s manifests — strict schema validation (k8s 1.30) | ✅ passed |
| Ansible playbook vs. Terraform-format generated files (ansible-core 2.17 and 2.20) | ✅ passed, no warnings |
| Terraform HCL parse; frontend JS syntax; YAML lint | ✅ passed |
| Docker image builds, `terraform init/apply`, Jenkins run, live cluster deploy | ⏳ **not run** — must be run on your machine (commands above) |

## Requirements checklist

| # | Requirement | Implemented by | Verify with |
|---|---|---|---|
| 1 | release-v1.0 branch, commits, merge to main, push | Section 1 commands | `git log --graph --all`, GitHub branches |
| 2 | Sprint complete, all Done, burndown reviewed | `jira/sprint-backlog.csv` + section 2 | Jira Burndown / Sprint Report |
| 3 | Declarative pipeline: build, test, package | `Jenkinsfile` | Jenkins Stage View + Test Result |
| 4 | Build, tag, run image, verified by `docker ps` | `backend/Dockerfile`, `frontend/Dockerfile`, section 4 | `docker ps --filter name=payment-` |
| 5 | Frontend + Backend on K8s via NodePort | `k8s/*.yaml` | `kubectl get svc -n payment-engine`, http://localhost:30080 |
| 6 | Terraform generates connection files; Ansible validates hosts | `terraform/`, `ansible/playbooks/validate-hosts.yml` | `terraform output`, PLAY RECAP `failed=0` |

## Cleanup (optional)

```powershell
docker rm -f payment-backend payment-frontend
docker network rm payments-net
kubectl delete namespace payment-engine
```
