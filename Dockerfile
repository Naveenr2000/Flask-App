# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the local code to the container
COPY . /app

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service account file for authentication (only if needed)
COPY project1-speech-to-text.json /app/project1-speech-to-text.json

# Expose port 8080 (Cloud Run's default port)
EXPOSE 8080

# Define the command to run your app using Flask
CMD ["python", "app.py"]
