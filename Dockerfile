FROM theosotr/sqlite3-reducer

USER root

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y python3-pip

RUN pip3 install -r requirements.txt --break-system-packages

RUN cp reducer /usr/bin/reducer && chmod +x /usr/bin/reducer