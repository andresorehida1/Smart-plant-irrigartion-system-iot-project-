FROM python:3.13-slim
WORKDIR /app

# Copia entradas y simuladores
COPY DeviceConnector.py ./
COPY simulators/ ./simulators/

# Instala CherryPy y MQTT
RUN pip install --no-cache-dir cherrypy paho-mqtt

# Exponer variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/simulators:${PYTHONPATH}"
ENV PORT=9090

CMD ["python", "DeviceConnector.py"]
