FROM docker-registry.centrofinans.ru/utils/ibase-micro:1.49.1
LABEL maintainer="v.onishchuk@centrofinans.ru"

COPY requirements.txt requirements.txt
RUN pip3 install \
      --no-cache-dir \
#       -i https://pypi.m.centrofinans.ru/simple/ \
      -r requirements.txt

COPY ["./source/", "/opt/service/"]

RUN chmod +x /opt/service/app.py

WORKDIR /opt/service
