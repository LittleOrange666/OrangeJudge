FROM python:3.12-alpine

WORKDIR /app

COPY tools/requirements.txt /app/

RUN pip3 install -r requirements.txt

COPY testlib /app/testlib
COPY main.py /app/
COPY templates /app/templates
COPY static /app/static
COPY modules /app/modules

CMD python3 main.py