# Imagen única parametrizada por servicio:
#   docker build --build-arg SERVICIO=ms_asistencia -t ms-asistencia .
#   docker build --build-arg SERVICIO=ms_validacion -t ms-validacion .
#   docker build --build-arg SERVICIO=ms_reportes  -t ms-reportes .
FROM python:3.12-slim

ARG SERVICIO
ENV SERVICIO=${SERVICIO} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MODO=gcp

WORKDIR /app

COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements/${SERVICIO}.txt

COPY common/ ./common/
COPY ml/ ./ml/
COPY services/__init__.py ./services/__init__.py
COPY services/${SERVICIO}/ ./services/${SERVICIO}/

# ms-validacion empaqueta un modelo base entrenado en la propia imagen (misma versión de scikit-learn)
RUN if [ "$SERVICIO" = "ms_validacion" ]; then python -m ml.entrenar_isolation_forest --salida ml/modelo/isolation_forest.joblib; fi

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

CMD ["sh", "-c", "exec uvicorn services.${SERVICIO}.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
