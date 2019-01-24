FROM python:3.5-stretch

RUN pip install discord irc3

RUN mkdir /app /app/defaults
COPY . /app/
COPY config/*.default /app/defaults/
WORKDIR /app
COPY config/permissions.json.default config/permissions.json

VOLUME /app/config

CMD [ "./docker-start.sh" ]