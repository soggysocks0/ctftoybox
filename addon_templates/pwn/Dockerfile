FROM ubuntu:22.04

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        gcc libc6-dev socat \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /chall
COPY chall.c .
COPY flag.txt /flag.txt

RUN gcc -no-pie -fno-stack-protector -z execstack -o chall chall.c \
 && chmod 755 chall \
 && chmod 644 /flag.txt

EXPOSE 31337
CMD ["socat", "TCP-LISTEN:31337,reuseaddr,fork", "EXEC:/chall/chall,stderr"]
