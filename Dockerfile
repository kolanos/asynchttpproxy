FROM python:3.5-alpine

RUN pip install --upgrade pip wheel

WORKDIR /app
COPY . /app

RUN pip install --no-cache --use-wheel -r requirements.txt \
    && chmod +x /app/bin/asynchttpproxy

CMD /app/bin/asynchttpproxy