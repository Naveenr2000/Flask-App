FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
COPY project1-speech-to-text.json /app/project1-speech-to-text.json 

CMD ["python", "app.py"]
# Expose port 8080 (Cloud Run's default port)
EXPOSE 8080