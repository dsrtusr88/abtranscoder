FROM python:3.9-slim

# Install necessary packages
RUN apt-get update && apt-get install -y git mktorrent flac lame sox ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Prepare application directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY . /app

# Ensure start script is executable
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
