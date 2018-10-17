FROM python:3.7-stretch

RUN mkdir /app
COPY . /app/

CMD [ "python3","/app/server.py" ]