FROM python:3.10

WORKDIR /presidio_cli

COPY Pipfile* .

RUN pip install --upgrade pip pipenv
RUN pipenv sync
RUN pip install pypdf

COPY . .

RUN cd /presidio_cli && \
    pip install -e /presidio_cli && \
    python -m spacy download en_core_web_sm && \
    python -m spacy download en_core_web_lg

ENTRYPOINT ["presidio"]
