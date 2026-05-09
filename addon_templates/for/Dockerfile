FROM python:3.12-slim

WORKDIR /app
COPY make_challenge.py .

RUN mkdir /out
ENV CHALL_FLAG="bluebox{for_custom_template}"
RUN python /app/make_challenge.py

# Players retrieve the artifact via:
#   docker cp <container>:/out/challenge.jpg .
CMD ["/bin/sh", "-c", "echo 'Image at /out/challenge.jpg — copy with: docker cp <container>:/out/challenge.jpg .'; tail -f /dev/null"]
