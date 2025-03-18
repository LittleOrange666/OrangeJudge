FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update &&\
    apt-get -y install sudo python3 python3-pip redis --fix-missing &&\
    apt-get clean && rm -rf /var/lib/apt/lists/* \

COPY tools/requirements.txt /app/

RUN pip3 install -r requirements.txt

COPY testlib /app/testlib
COPY static /app/static
COPY templates /app/templates
COPY modules /app/modules
COPY main.py /app/

CMD python3 main.py