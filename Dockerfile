# Use a base image with Python
FROM python:3.11-slim

# Install FFmpeg and other necessary packages
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements.txt into the working directory
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code into the working directory
COPY . .

# Execute the Python script
CMD ["python", "radio.py"]
