# Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install grpc
RUN pip install --no-cache-dir grpcio grpcio-tools

# Copy proto and generated pb files or generate at build
COPY proto/tx.proto /app/proto/tx.proto

# Generate pb2 code
RUN python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. ./proto/tx.proto

# Copy python code
COPY node /app
COPY coordinator /app/coordinator
COPY node/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
CMD ["/app/entrypoint.sh"]
