FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update \
    && \
    apt install -y \
        rsync \
        less \
        vim \
        build-essential \
        python3 \
        python3-dev \
        python3-pip \
        python3-markdown \
        libmariadb-dev \
        libmariadb-dev-compat \
        mariadb-client \
        libexpat1 apache2 apache2-utils ssl-cert \
        libapache2-mod-wsgi-py3 \
        unzip \
        bzip2

# RUN ln -s /usr/bin/python3 /usr/bin/python

# Compile and install EMDROS software

ARG emdrosversion="3.9.0"

WORKDIR /build
COPY src/emdros .
RUN tar xfzv emdros-${emdrosversion}.tar.gz

WORKDIR emdros-${emdrosversion}
RUN ./configure \
    --prefix=/usr/local \
    --with-sqlite3=no \
    --with-mysql=yes \
    --with-swig-language-java=no \
    --with-swig-language-python2=no \
    --with-swig-language-python3=yes \
    --with-postgresql=no \
    --with-wx=no \
    --with-swig-language-csharp=no \
    --with-swig-language-php7=no \
    --with-bpt=no \
    --disable-debug && \
    make && \
    make install

RUN cd /usr/local/lib/python3.12/dist-packages \
    && \
    for f in /usr/local/lib/emdros/*Emdros*; do ln -s $f; done  \
    && \
    cd - && \
    ldconfig

WORKDIR /etc/apache2
COPY src/apache/wsgi.conf mods-available 
COPY src/apache/shebanq.conf sites-available 
RUN ln -sf ../mods-available/expires.load mods-enabled \
    && \
    ln -sf ../mods-available/headers.load mods-enabled \
    && \
    ln -sf ../sites-available/shebanq.conf sites-enabled/shebanq.conf

# Install additional software

WORKDIR /app
