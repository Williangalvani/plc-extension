FROM python:3.11-slim as base

RUN apt update && apt install -y gcc build-essential git && git clone https://github.com/qca/open-plc-utils.git && cd open-plc-utils && make && make install && apt remove -y gcc build-essential git && apt autoremove -y

FROM base

COPY app/setup.py /app/setup.py
RUN cd /app && python -m pip install --extra-index-url https://www.piwheels.org/simple .
COPY app /app


LABEL version="v0.0.5"

ARG IMAGE_NAME

LABEL permissions='\
{\
  "NetworkMode": "host",\
  "HostConfig": {\
    "Privileged": true,\
    "NetworkMode": "host",\
    "Binds": [\
      "/proc:/proc:ro"\
    ]\
  }\
}'

ARG AUTHOR
ARG AUTHOR_EMAIL
LABEL authors='[\
    {\
        "name": "Willian Galvani",\
        "email": "wiliangalvani@gmail.com"\
    }\
]'

ARG MAINTAINER
ARG MAINTAINER_EMAIL
LABEL company='{\
        "about": "",\
        "name": "Willian Galvani",\
        "email": "wiliangalvani@gmail.com"\
    }'
LABEL type="tool"
ARG REPO
ARG OWNER
LABEL readme='https://raw.githubusercontent.com/williangalvani/plc-extension/{tag}/README.md'
LABEL links='{\
        "source": "https://github.com/williangalvani/plc-extension"\
    }'
LABEL requirements="core >= 1.1"

ENTRYPOINT cd app && python main.py
