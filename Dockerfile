FROM ubuntu:latest
# Build with: docker build -t austinjhunt/py-tcp-over-udp .
# Push with: docker push austinjhunt/py-tcp-over-udp

RUN apt update && apt -y upgrade && apt install -y net-tools python3 gcc
RUN apt install -y python3-dev python3-pip net-tools telnet iputils-ping
RUN DEBIAN_FRONTEND="noninteractive" apt install -y default-jre default-jdk
RUN python3 -m pip install --upgrade pip
ADD requirements.txt /
RUN pip install -r /requirements.txt

ADD messages /messages
ADD src /src
WORKDIR /src/




