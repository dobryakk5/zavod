# Kubernetes Deployment

В этом документе описана настройка и деплоймент системы Zavod в Kubernetes.

## Содержание

- [Требования](#требования)
- [Архитектура](#архитектура)
- [Подготовка](#подготовка)
- [Манифесты](#манифесты)
- [Деплоймент](#деплоймент)
- [Мониторинг](#мониторинг)
- [Scaling](#scaling)
- [Backup и Recovery](#backup-и-recovery)

## Требования

1. **Kubernetes cluster** (minikube, kubeadm, cloud provider)
2. **kubectl** - Kubernetes CLI
3. **Helm** (опционально)
4. **Container Registry** (Docker Hub, Google Container Registry, и т.д.)
5. **Ingress Controller** (nginx-ingress, traefik)
6. **Storage Class** для persistent volumes

## Архитектура

### Компоненты

```
Kubernetes Cluster
├── Namespace: zavod
├── Backend (Django)
│   ├── Deployment
│   ├── Service (ClusterIP)
│   └── ConfigMap (settings)
├── Frontend (Next.js)
│   ├── Deployment
│   ├── Service (ClusterIP)
│   └── ConfigMap (env vars)
├── AI Worker (Celery)
│   ├── Deployment
│   └── ConfigMap
├── PostgreSQL
│   ├── StatefulSet
│   ├── Service
│   └── PersistentVolumeClaim
├── Redis
│   ├── Deployment
│   ├── Service
│   └── PersistentVolumeClaim
├── Ingress
│   └── TLS termination
└── Monitoring
    ├── Prometheus
    ├── Grafana
    └── AlertManager
```

### Сетевая архитектура

```
Internet
    ↓
Ingress Controller (nginx)
    ↓
├── api.zavod.example.com → Backend Service
├── app.zavod.example.com → Frontend Service
└── monitor.zavod.example.com → Grafana Service
```

## Подготовка

### 1. Сборка Docker образов

```bash
# Сборка backend
cd backend
docker build -t your-registry/zavod-backend:v1.0.0 .
docker push your-registry/zavod-backend:v1.0.0

# Сборка frontend
cd frontend
docker build -t your-registry/zavod-frontend:v1.0.0 .
docker push your-registry/zavod-frontend:v1.0.0

# Сборка ai-worker
cd ai-worker
docker build -t your-registry/zavod-ai-worker:v1.0.0 .
docker push your-registry/zavod-ai-worker:v1.0.0
```

### 2. Подготовка кластера

```bash
# Создание namespace
kubectl create namespace zavod

# Установка ingress-nginx (если не установлен)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Создание storage class (если не существует)
kubectl apply -f k8s/storage-class.yaml
```

### 3. Секреты

```bash
# Создание секретов
kubectl create secret generic zavod-secrets \
  --namespace=zavod \
  --from-literal=django-secret-key='your-super-secret-django-key' \
  --from-literal=db-password='your-secure-db-password' \
  --from-literal=redis-password='your-secure-redis-password' \
  --from-literal=postgres-password='your-secure-postgres-password' \
  --from-literal=openai-api-key='your-openai-api-key' \
  --from-literal=stability-api-key='your-stability-api-key' \
  --from-literal=runway-api-key='your-runway-api-key' \
  --from-literal=telegram-bot-token='your-telegram-bot-token' \
  --from-literal=instagram-access-token='your-instagram-token' \
  --from-literal=youtube-client-id='your-youtube-client-id' \
  --from-literal=youtube-client-secret='your-youtube-client-secret'

# Создание TLS сертификата
kubectl create secret tls zavod-tls \
  --namespace=zavod \
  --cert=path/to/fullchain.pem \
  --key=path/to/privkey.pem
```

## Манифесты

### 1. PostgreSQL

```yaml
# k8s/postgres/postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: zavod
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: zavod
        - name: POSTGRES_USER
          value: zavod_user
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: postgres-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - zavod_user
            - -d
            - zavod
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - zavod_user
            - -d
            - zavod
          initialDelaySeconds: 5
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 20Gi

---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: zavod
spec:
  selector:
    app: postgres
  ports:
  - protocol: TCP
    port: 5432
    targetPort: 5432
  type: ClusterIP
```

### 2. Redis

```yaml
# k8s/redis/redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: zavod
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - /etc/redis/redis.conf
        - --requirepass
        - $(REDIS_PASSWORD)
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: redis-password
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-storage
          mountPath: /data
        - name: redis-config
          mountPath: /etc/redis
        livenessProbe:
          exec:
            command:
            - redis-cli
            - -a
            - $(REDIS_PASSWORD)
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - redis-cli
            - -a
            - $(REDIS_PASSWORD)
            - ping
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
      - name: redis-config
        configMap:
          name: redis-config

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: zavod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 5Gi

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
  namespace: zavod
data:
  redis.conf: |
    maxmemory 512mb
    maxmemory-policy allkeys-lru
    appendonly yes

---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: zavod
spec:
  selector:
    app: redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379
  type: ClusterIP
```

### 3. Backend

```yaml
# k8s/backend/backend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: zavod
  labels:
    app: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: your-registry/zavod-backend:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DEBUG
          value: "False"
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: django-secret-key
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: db-password
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: redis-password
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: openai-api-key
        - name: STABILITY_API_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: stability-api-key
        - name: RUNWAY_API_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: runway-api-key
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: telegram-bot-token
        envFrom:
        - configMapRef:
            name: backend-config
        livenessProbe:
          httpGet:
            path: /api/health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: zavod
spec:
  selector:
    app: backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
  namespace: zavod
data:
  DATABASE_URL: "postgres://zavod_user:$(DB_PASSWORD)@postgres:5432/zavod"
  REDIS_URL: "redis://:$(REDIS_PASSWORD)@redis:6379/0"
  CELERY_BROKER_URL: "redis://:$(REDIS_PASSWORD)@redis:6379/0"
  CELERY_RESULT_BACKEND: "redis://:$(REDIS_PASSWORD)@redis:6379/0"
  ALLOWED_HOSTS: "api.zavod.example.com"
```

### 4. Frontend

```yaml
# k8s/frontend/frontend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: zavod
  labels:
    app: frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: your-registry/zavod-frontend:v1.0.0
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_URL
          value: "https://api.zavod.example.com"
        - name: NEXT_PUBLIC_DEV_MODE
          value: "false"
        livenessProbe:
          httpGet:
            path: /
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"

---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: zavod
spec:
  selector:
    app: frontend
  ports:
  - protocol: TCP
    port: 3000
    targetPort: 3000
  type: ClusterIP
```

### 5. AI Worker

```yaml
# k8s/ai-worker/ai-worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-worker
  namespace: zavod
  labels:
    app: ai-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-worker
  template:
    metadata:
      labels:
        app: ai-worker
    spec:
      containers:
      - name: ai-worker
        image: your-registry/zavod-ai-worker:v1.0.0
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: db-password
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: redis-password
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: openai-api-key
        - name: STABILITY_API_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: stability-api-key
        - name: RUNWAY_API_KEY
          valueFrom:
            secretKeyRef:
              name: zavod-secrets
              key: runway-api-key
        envFrom:
        - configMapRef:
            name: backend-config
        command: ["celery", "-A", "config", "worker", "-l", "info", "-c", "2"]
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

### 6. Ingress

```yaml
# k8s/ingress/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: zavod-ingress
  namespace: zavod
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - api.zavod.example.com
    - app.zavod.example.com
    - monitor.zavod.example.com
    secretName: zavod-tls
  rules:
  - host: api.zavod.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
  - host: app.zavod.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 3000
  - host: monitor.zavod.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: grafana
            port:
              number: 3000
```

## Деплоймент

### 1. Применение манифестов

```bash
# Применение всех манифестов
kubectl apply -f k8s/storage-class.yaml
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/redis/
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/
kubectl apply -f k8s/ai-worker/
kubectl apply -f k8s/ingress/

# Проверка состояния
kubectl get all -n zavod
kubectl get pvc -n zavod
kubectl get ingress -n zavod
```

### 2. Миграции Django

```bash
# Выполнение миграций
kubectl exec -it deployment/backend -n zavod -- python manage.py migrate

# Создание суперпользователя (опционально)
kubectl exec -it deployment/backend -n zavod -- python manage.py createsuperuser
```

### 3. Проверка работоспособности

```bash
# Проверка подключения к базе данных
kubectl exec -it deployment/backend -n zavod -- pg_isready -h postgres -U zavod_user -d zavod

# Проверка Redis
kubectl exec -it deployment/backend -n zavod -- redis-cli -h redis ping

# Проверка Celery
kubectl exec -it deployment/ai-worker -n zavod -- celery -A config inspect ping
```

## Мониторинг

### 1. Prometheus

```yaml
# k8s/monitoring/prometheus.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: zavod
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:v2.47.0
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: prometheus-config
          mountPath: /etc/prometheus
        - name: prometheus-storage
          mountPath: /prometheus
        command:
        - prometheus
        - --config.file=/etc/prometheus/prometheus.yml
        - --storage.tsdb.path=/prometheus
        - --web.console.libraries=/etc/prometheus/console_libraries
        - --web.console.templates=/etc/prometheus/consoles
        - --storage.tsdb.retention.time=200h
        - --web.enable-lifecycle
      volumes:
      - name: prometheus-config
        configMap:
          name: prometheus-config
      - name: prometheus-storage
        persistentVolumeClaim:
          claimName: prometheus-pvc

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: prometheus-pvc
  namespace: zavod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 10Gi

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: zavod
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    
    scrape_configs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
        - role: pod
          namespaces:
            names:
            - zavod
        relabel_configs:
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
          action: keep
          regex: true
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
          action: replace
          target_label: __metrics_path__
          regex: (.+)

---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: zavod
spec:
  selector:
    app: prometheus
  ports:
  - protocol: TCP
    port: 9090
    targetPort: 9090
  type: ClusterIP
```

### 2. Grafana

```yaml
# k8s/monitoring/grafana.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: zavod
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:10.1.0
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          value: "admin"
        volumeMounts:
        - name: grafana-storage
          mountPath: /var/lib/grafana
        - name: grafana-config
          mountPath: /etc/grafana/provisioning
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
      volumes:
      - name: grafana-storage
        persistentVolumeClaim:
          claimName: grafana-pvc
      - name: grafana-config
        configMap:
          name: grafana-config

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: grafana-pvc
  namespace: zavod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 5Gi

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-config
  namespace: zavod
data:
  datasources.yaml: |
    apiVersion: 1
    datasources:
    - name: Prometheus
      type: prometheus
      access: proxy
      url: http://prometheus:9090
      isDefault: true

---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: zavod
spec:
  selector:
    app: grafana
  ports:
  - protocol: TCP
    port: 3000
    targetPort: 3000
  type: ClusterIP
```

### 3. ServiceMonitor (опционально)

```yaml
# k8s/monitoring/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: zavod-apps
  namespace: zavod
  labels:
    app: zavod
spec:
  selector:
    matchLabels:
      app: backend
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
---
apiVersion: v1
kind: Service
metadata:
  name: backend-metrics
  namespace: zavod
  labels:
    app: backend
    prometheus_io_scrape: "true"
    prometheus_io_port: "8000"
    prometheus_io_path: "/metrics"
spec:
  selector:
    app: backend
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  type: ClusterIP
```

## Scaling

### 1. Horizontal Pod Autoscaler

```yaml
# k8s/hpa/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: zavod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
  namespace: zavod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-worker-hpa
  namespace: zavod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-worker
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80
```

### 2. Manual Scaling

```bash
# Увеличение количества реплик
kubectl scale deployment backend -n zavod --replicas=5
kubectl scale deployment frontend -n zavod --replicas=5
kubectl scale deployment ai-worker -n zavod --replicas=3

# Проверка количества реплик
kubectl get deployments -n zavod
```

## Backup и Recovery

### 1. PostgreSQL Backup

```yaml
# k8s/backup/postgres-backup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: zavod
spec:
  schedule: "0 2 * * *"  # Ежедневно в 2:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:15
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h postgres -U zavod_user -d zavod > /backup/backup_$(date +%Y%m%d_%H%M%S).sql
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: zavod-secrets
                  key: postgres-password
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
            resources:
              requests:
                memory: "128Mi"
                cpu: "100m"
              limits:
                memory: "256Mi"
                cpu: "200m"
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: backup-pvc
  namespace: zavod
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 50Gi
```

### 2. Backup Script

```bash
#!/bin/bash
# backup.sh

NAMESPACE="zavod"
BACKUP_DIR="/tmp/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "Starting backup..."

# PostgreSQL backup
kubectl exec -n $NAMESPACE deployment/postgres -- pg_dump -U zavod_user zavod > $BACKUP_DIR/postgres_$DATE.sql

# Redis backup
kubectl exec -n $NAMESPACE deployment/redis -- redis-cli BGSAVE
sleep 5
kubectl cp $NAMESPACE/$(kubectl get pods -n $NAMESPACE -l app=redis -o jsonpath='{.items[0].metadata.name}'):/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Архивация
tar -czf $BACKUP_DIR/zavod_backup_$DATE.tar.gz -C $BACKUP_DIR postgres_$DATE.sql redis_$DATE.rdb

# Очистка временных файлов
rm $BACKUP_DIR/postgres_$DATE.sql $BACKUP_DIR/redis_$DATE.rdb

echo "Backup completed: $BACKUP_DIR/zavod_backup_$DATE.tar.gz"
```

### 3. Recovery Script

```bash
#!/bin/bash
# restore.sh

NAMESPACE="zavod"
BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

echo "Starting restore from $BACKUP_FILE..."

# Распаковка архива
TEMP_DIR="/tmp/restore_$(date +%s)"
mkdir -p $TEMP_DIR
tar -xzf $BACKUP_FILE -C $TEMP_DIR

# PostgreSQL restore
kubectl exec -n $NAMESPACE -i deployment/postgres -- psql -U zavod_user -d zavod < $TEMP_DIR/postgres_*.sql

# Redis restore
kubectl cp $TEMP_DIR/redis_*.rdb $NAMESPACE/$(kubectl get pods -n $NAMESPACE -l app=redis -o jsonpath='{.items[0].metadata.name}'):/data/
kubectl exec -n $NAMESPACE deployment/redis -- redis-cli BGREWRITEAOF

# Очистка
rm -rf $TEMP_DIR

echo "Restore completed"
```

### 4. Disaster Recovery

```bash
# disaster-recovery.sh

NAMESPACE="zavod"
BACKUP_BUCKET="gs://your-backup-bucket"

echo "Starting disaster recovery..."

# Восстановление из облака
gsutil cp $BACKUP_BUCKET/latest_backup.tar.gz /tmp/
tar -xzf /tmp/latest_backup.tar.gz -C /tmp/

# Запуск скрипта восстановления
./restore.sh /tmp/latest_backup.tar.gz

echo "Disaster recovery completed"
```

---

**Далее:**
- [Docker Deployment](./docker.md) - Docker deployment
- [AWS Deployment](./aws.md) - AWS deployment
- [Monitoring](../08-guides/best-practices.md) - Best practices
