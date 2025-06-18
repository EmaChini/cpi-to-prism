FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y \
        iputils-ping \
        graphviz \
        graphviz-dev \
        curl \
        default-jdk \
        make \
        gcc \
        g++ \
        git \
        wget \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN cd /opt && \
    wget -O prism.tar.gz https://www.prismmodelchecker.org/dl/prism-4.8.1-linux64-x86.tar.gz && \
    echo "Verifying download..." && \
    tar xzf prism.tar.gz && \
    rm prism.tar.gz && \
    mv prism-* prism && \
    cd prism && \
    ./install.sh

ENV PATH="/opt/prism/bin:${PATH}"
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install jupyter


COPY . /app 

EXPOSE 8888

CMD sh -c "jupyter notebook --notebook-dir=/app --ip=0.0.0.0 --port=8888 --no-browser --allow-root --IdentityProvider.token='' & exec python3 sources"
