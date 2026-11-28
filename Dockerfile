# Dockerfile

# Use the official Python image with the desired version
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt /app

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . /app
# Command to run your application
CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --reload"