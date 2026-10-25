# Static dashboard served by nginx; /api/* is reverse-proxied to the backend.
# BACKEND_HOST/BACKEND_PORT are substituted into the nginx template at start-up
# by the official image's envsubst entrypoint. "payment-backend" resolves as the
# container name on the Docker network AND as the Kubernetes Service name.
FROM nginx:1.27-alpine
ENV BACKEND_HOST=payment-backend \
    BACKEND_PORT=5000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY public/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz || exit 1
