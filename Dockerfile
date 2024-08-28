# Use a base Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /usr/src/app

# Copy requirements.txt into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application files
COPY . .

# Specify the command to run your application
CMD ["python", "main.py"]