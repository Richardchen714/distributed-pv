FROM python:3.11
WORKDIR /app

COPY . .
# RUN pip install -r requirements.txt

ENV PYTHONPATH="/app"

CMD ["python", "raft/raft_server.py"]
