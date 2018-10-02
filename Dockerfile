FROM jfloff/alpine-python:3.6

RUN apk update
RUN apk add libffi-dev

RUN mkdir -p /opt/tmper
ADD ./ /opt/tmper
RUN cd /opt/tmper && python setup.py install

EXPOSE 3333
CMD tmper s -p 3333
