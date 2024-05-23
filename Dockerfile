FROM python:3.11-slim

COPY app /app
RUN python -m pip install /app --extra-index-url https://www.piwheels.org/simple
RUN apt update && apt install -y gcc build-essential git && git clone https://github.com/qca/open-plc-utils.git && cd open-plc-utils && make && make install && apt remove -y gcc build-essential git && apt autoremove -y


LABEL version="0.0.3"

ARG IMAGE_NAME

LABEL permissions='\
{\
  "NetworkMode": "host",\
  "HostConfig": {\
    "Privileged": true,\
    "NetworkMode": "host"\
  }\
}'

ARG AUTHOR
ARG AUTHOR_EMAIL
LABEL authors='[\
    {\
        "name": "$AUTHOR",\
        "email": "$AUTHOR_EMAIL"\
    }\
]'

ARG MAINTAINER
ARG MAINTAINER_EMAIL
LABEL company='{\
        "about": "",\
        "name": "$MAINTAINER",\
        "email": "$MAINTAINER_EMAIL"\
    }'
LABEL type="example"
ARG REPO
ARG OWNER
LABEL readme='https://raw.githubusercontent.com/$OWNER/$REPO/{tag}/README.md'
LABEL links='{\
        "source": "https://github.com/$OWNER/$REPO"\
    }'
LABEL requirements="core >= 1.1"

ENTRYPOINT cd app && python main.py
