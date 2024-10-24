FROM python:3.13-bookworm
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir /app/defaults
COPY config/*.default /app/defaults/

COPY config/permissions.json.default config/permissions.json

VOLUME /app/config

CMD [ "./docker-start.sh" ]