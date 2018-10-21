FROM python:3.5-stretch

RUN pip install discord irc3

RUN mkdir /app
COPY . /app/
WORKDIR /app
COPY config/permissions.json.default app/config/permissions.json

VOLUME /app/config

CMD [ "python3","./server.py" ]