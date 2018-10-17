FROM python:3.5-stretch

RUN pip install discord

RUN mkdir /app
COPY . /app/
WORKDIR /app

CMD [ "python3","./server.py" ]