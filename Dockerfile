FROM python:3.5-stretch

RUN pip install discord irc3

RUN mkdir /app
COPY . /app/
WORKDIR /app

VOLUME /app/config

CMD [ "python3","./server.py" ]