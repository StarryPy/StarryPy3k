FROM python:3.7-stretch

RUN mkdir /app
COPY * /app

ENTRYPOINT [ "python3","/app/server.py"]