ARG PYTHON_IMAGE

FROM alpine:3.14 as fetcher

ARG TARGETARCH
ARG POETRY_VERSION

RUN apk add --no-cache curl
RUN case ${TARGETARCH} in \
        "amd64")  R_ARCH=x86_64  ;; \
        "arm64")  R_ARCH=aarch64  ;; \
    esac && \
    curl -sSL https://github.com/gi0baro/poetry-bin/releases/download/${POETRY_VERSION}/poetry-bin-${POETRY_VERSION}-${R_ARCH}-unknown-linux-gnu.tar.gz > poetry-bin.tar.gz
RUN mkdir -p /opt/poetry_bin && tar xzf poetry-bin.tar.gz --directory /opt/poetry_bin

FROM python:${PYTHON_IMAGE}

COPY --from=fetcher /opt/poetry_bin /opt/poetry_bin

RUN ln -s /opt/poetry_bin/poetry /usr/bin/poetry

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1
