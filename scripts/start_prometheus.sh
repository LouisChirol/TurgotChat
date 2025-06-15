   # Download Prometheus
   wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
   tar xvfz prometheus-*.tar.gz
   cd prometheus-*
   
   # Copy the config file
   cp ../backend/prometheus.yml .
   
   # Start Prometheus
   ./prometheus --config.file=prometheus.yml