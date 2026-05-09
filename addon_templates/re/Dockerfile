# Reverse Engineering challenge template — customizable.
# Compiles chall.c with debug-friendly flags so the binary is reasonable
# to reverse. Adjust as needed.

FROM gcc:12-bookworm AS builder
WORKDIR /build
COPY chall.c .
RUN gcc -O0 -no-pie -fno-stack-protector -o chall chall.c

FROM debian:bookworm-slim
COPY --from=builder /build/chall /chall
CMD ["/bin/sh", "-c", "echo 'Binary at /chall — copy with: docker cp <container>:/chall .'; tail -f /dev/null"]
