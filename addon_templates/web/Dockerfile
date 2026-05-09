FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3

COPY app.py .
# CTF Manager will set CHALL_FLAG at deploy time. The default below is
# only used if you build the image directly without going through CTF Manager.
ENV CHALL_FLAG="bluebox{web_custom_template}"

EXPOSE 8080
CMD ["python", "app.py"]
