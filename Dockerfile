# Use the official Python image from Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install required system packages (e.g., FFmpeg for audio conversion)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy the local code to the container
COPY . /app

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y ffmpeg


# Expose port 8080 (Cloud Run's default port)
EXPOSE 8080

# Define the command to run your app
CMD ["python", "app.py"]
