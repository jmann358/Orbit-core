# Build only after owner approval; no project/candidate code in this context.
FROM docker.io/library/python@sha256:55432fc4ef6d07e33c10449312f0ec00071bbb310bb9bd7ba626a31fbbc2cb0d AS wheels
COPY requirements.lock /recipe/requirements.lock
RUN python -m pip --isolated download --disable-pip-version-check --no-cache-dir --only-binary=:all: --require-hashes --dest /wheels -r /recipe/requirements.lock

FROM docker.io/library/python@sha256:55432fc4ef6d07e33c10449312f0ec00071bbb310bb9bd7ba626a31fbbc2cb0d
COPY --from=wheels /wheels /wheels
COPY requirements.lock /opt/orbit-test/requirements.lock
RUN --network=none python -m pip --isolated install --disable-pip-version-check --no-cache-dir --only-binary=:all: --require-hashes --no-index --find-links=/wheels -r /opt/orbit-test/requirements.lock && rm -rf /wheels
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HOME=/tmp TMPDIR=/tmp
RUN mkdir /work && chmod 0555 /work
USER 10001:10001
WORKDIR /work
ENTRYPOINT []
CMD ["python", "--version"]
