FROM python:3.12-slim-bullseye

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install exiftool
RUN apt update
RUN apt install -y exiftool

# Copy the rest of the application
COPY . .

# Set the entrypoint
ENTRYPOINT ["python", "src/main.py"]
CMD ["--inputDir", "/app/input", "--outputDir", "/app/output"]