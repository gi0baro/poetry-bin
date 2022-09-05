ARG PYTHON_IMAGE

FROM python:${PYTHON_IMAGE} as glibc

ENV GLIBC_REPO=https://github.com/sgerrand/alpine-pkg-glibc
ENV GLIBC_VERSION=2.33-r0

RUN apk add --no-cache curl
RUN curl -sSL ${GLIBC_REPO}/releases/download/${GLIBC_VERSION}/glibc-${GLIBC_VERSION}.apk -o glibc.apk
RUN curl -sSL ${GLIBC_REPO}/releases/download/${GLIBC_VERSION}/glibc-bin-${GLIBC_VERSION}.apk -o glibc-bin.apk
RUN apk add --allow-untrusted glibc.apk glibc-bin.apk

FROM alpine:3.14 as fetcher

ARG POETRY_VERSION

RUN apk add --no-cache curl
RUN curl -sSL https://github.com/gi0baro/poetry-bin/releases/download/${POETRY_VERSION}/poetry-bin-${POETRY_VERSION}-x86_64-unknown-linux-gnu.tar.gz > poetry-bin.tar.gz
RUN mkdir -p /opt/poetry_bin && tar xzf poetry-bin.tar.gz --directory /opt/poetry_bin

FROM python:${PYTHON_IMAGE}

COPY --from=glibc /usr/glibc-compat /usr/glibc-compat
COPY --from=fetcher /opt/poetry_bin /opt/poetry_bin

RUN apk add --no-cache libgcc
RUN mkdir -p /lib64
RUN ln -s /usr/glibc-compat/lib/ld-linux-x86-64.so.2 /lib/ld-linux-x86-64.so.2
RUN ln -s /usr/glibc-compat/lib/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2
RUN ln -s /opt/poetry_bin/bin/poetry /bin/poetry

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1
