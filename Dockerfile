FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update &&\
    apt-get -y install sudo python3 python3-pip redis --fix-missing &&\
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY \
    testlib \
    static \
    templates \
    modules \
    main.py \
    tools/requirements.txt \
    /app/

RUN pip3 install -r requirements.txt

CMD python3 main.py